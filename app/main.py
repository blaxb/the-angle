# app/main.py
import time
from urllib.parse import quote_plus
from datetime import datetime

import httpx
from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlmodel import Session, select
from sqlalchemy import delete, text

from .db import init_db, get_session, engine
from .models import User, Post, CategorySummary
from .auth import (
    hash_password,
    verify_password,
    make_session_token,
    COOKIE_NAME,
    MAX_AGE_SECONDS,
    get_current_user,
)
from .ingest_reddit import fetch_reddit_search
from .ingest_x import fetch_x_recent
from .summarizer import summarize_category
from .stripe_billing import create_checkout_session
from .settings import settings

app = FastAPI(title="The Angle")
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


def compute_heat(score: int, comments: int, created_utc: int) -> float:
    now = int(time.time())
    age_hours = max(1.0, (now - created_utc) / 3600.0)
    return (score * 0.6 + comments * 2.0) / (age_hours ** 0.8)


def naive_category(title: str) -> str:
    t = (title or "").lower()
    if any(k in t for k in ["intern", "resume", "interview", "recruit"]):
        return "careers"
    if any(k in t for k in ["stock", "options", "trading", "crypto", "market", "earnings"]):
        return "markets"
    if any(k in t for k in ["startup", "saas", "churn", "mrr", "founder", "fundraising"]):
        return "startups"
    if any(k in t for k in ["python", "java", "react", "fastapi", "api", "docker", "kubernetes"]):
        return "coding"
    if any(k in t for k in ["food", "recipe", "cooking", "nutrition", "diet"]):
        return "food"
    return "misc"


@app.on_event("startup")
def on_startup():
    init_db()
    # SQLite pragmas to reduce "database is locked" during writes
    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.execute(text("PRAGMA synchronous=NORMAL;"))
            conn.execute(text("PRAGMA busy_timeout=5000;"))
            conn.commit()
    except Exception:
        pass


def render(request: Request, name: str, ctx: dict):
    ctx["request"] = request
    ctx["year"] = datetime.utcnow().year
    return templates.TemplateResponse(name, ctx)


def is_secure_request(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"


@app.get("/", response_class=HTMLResponse)
def root(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    return RedirectResponse(url="/dashboard" if user else "/pricing", status_code=302)


@app.get("/pricing", response_class=HTMLResponse)
def pricing(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    return render(request, "pricing.html", {"user": user})


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    err = request.query_params.get("err")
    error = "Account already exists. Try logging in." if err == "exists" else None
    return render(request, "register.html", {"user": user, "error": error})


@app.post("/register")
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    email = email.strip().lower()
    password = password.strip()
    if session.exec(select(User).where(User.email == email)).first():
        return RedirectResponse("/register?err=exists", status_code=302)

    u = User(email=email, password_hash=hash_password(password))
    session.add(u)
    session.commit()
    session.refresh(u)

    resp = RedirectResponse("/dashboard", status_code=302)
    resp.set_cookie(
        COOKIE_NAME,
        make_session_token(u.id),
        httponly=True,
        samesite="lax",
        secure=is_secure_request(request),
        max_age=MAX_AGE_SECONDS,
        path="/",
    )
    return resp


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    err = request.query_params.get("err")
    error = "Invalid login." if err else None
    return render(request, "login.html", {"user": user, "error": error})


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    email = email.strip().lower()
    password = password.strip()
    u = session.exec(select(User).where(User.email == email)).first()
    if not u or not verify_password(password, u.password_hash):
        return RedirectResponse("/login?err=1", status_code=302)

    resp = RedirectResponse("/dashboard", status_code=302)
    resp.set_cookie(
        COOKIE_NAME,
        make_session_token(u.id),
        httponly=True,
        samesite="lax",
        secure=is_secure_request(request),
        max_age=MAX_AGE_SECONDS,
        path="/",
    )
    return resp


@app.get("/logout")
def logout(request: Request):
    resp = RedirectResponse("/pricing", status_code=302)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, category: str | None = None, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    # Category counts
    cats = session.exec(select(Post.category)).all()
    counts = {}
    for c in cats:
        counts[c] = counts.get(c, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    # Summaries
    summaries = {s.category: s.summary for s in session.exec(select(CategorySummary)).all()}
    categories = [{"name": k, "count": v, "summary": summaries.get(k)} for k, v in ranked]
    if category:
        categories = [c for c in categories if c["name"] == category]

    if category:
        q = select(Post).where(Post.category == category).order_by(Post.heat_score.desc()).limit(40)
    else:
        q = select(Post).order_by(Post.heat_score.desc()).limit(40)
    posts = list(session.exec(q).all())

    return render(
        request,
        "dashboard.html",
        {
            "user": user,
            "categories": categories[:40],
            "posts": posts,
            "selected_category": category,
            "msg": request.query_params.get("msg"),
        },
    )


@app.post("/ingest/all")
async def ingest_all(
    request: Request,
    topics: str = Form(...),
    session: Session = Depends(get_session),
):
    """
    One button: ingests Reddit conversations + optional X recent search, then updates AI summaries.
    """
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    topic_list = [topic.strip() for topic in topics.split(",") if topic.strip()]
    if not topic_list:
        return RedirectResponse("/dashboard?msg=Add+at+least+one+topic", status_code=302)
    inserted_reddit = 0
    inserted_x = 0
    x_status = None

    # Reset previous ingest results so categories match requested topics
    session.exec(delete(CategorySummary))
    session.exec(delete(Post))
    session.commit()

    x_category = topic_list[0].lower() if len(topic_list) == 1 else "mixed"

    # --- Ingest (avoid premature autoflush during big loops) ---
    with session.no_autoflush:
        # Reddit
        for topic in topic_list:
            posts = await fetch_reddit_search(topic, sort="hot", limit=25, conversations_only=True)
            for p in posts:
                existing = session.exec(
                    select(Post).where(Post.source == "reddit", Post.source_id == p["source_id"])
                ).first()
                if existing:
                    continue

                cat = topic.lower()
                session.add(
                    Post(
                        source="reddit",
                        source_id=p["source_id"],
                        category=cat,
                        title=p["title"],
                        url=p["url"],
                        author=p.get("author"),
                        created_utc=p["created_utc"],
                        score=p["score"],
                        num_comments=p["num_comments"],
                        heat_score=compute_heat(p["score"], p["num_comments"], p["created_utc"]),
                    )
                )
                inserted_reddit += 1

        # X (optional)
        if topic_list and settings.x_bearer_token:
            try:
                x_query = " OR ".join(topic_list)
                raw = await fetch_x_recent(
                    query=x_query.strip(),
                    bearer_token=settings.x_bearer_token,
                    max_results=25,
                )
                now = int(time.time())
                for p in raw:
                    existing = session.exec(
                        select(Post).where(Post.source == "x", Post.source_id == p["source_id"])
                    ).first()
                    if existing:
                        continue

                    cat = x_category
                    session.add(
                        Post(
                            source="x",
                            source_id=p["source_id"],
                            category=cat,
                            title=p["title"],
                            url=p["url"],
                            author=p.get("author"),
                            created_utc=now,
                            score=p["score"],
                            num_comments=p["num_comments"],
                            heat_score=compute_heat(p["score"], p["num_comments"], now),
                        )
                    )
                    inserted_x += 1
            except httpx.HTTPStatusError as exc:
                x_status = f"X skipped ({exc.response.status_code})"
            except httpx.RequestError:
                x_status = "X skipped (network error)"

    # Commit inserts first
    session.commit()

    # --- AI summaries (no tiers in-build; later we’ll gate behind Stripe paid) ---
    try:
        categories = session.exec(select(Post.category)).all()
        unique = sorted(set([c for c in categories if c]))

        for cat in unique:
            titles = [
                p.title
                for p in session.exec(
                    select(Post)
                    .where(Post.category == cat)
                    .order_by(Post.heat_score.desc())
                    .limit(30)
                ).all()
            ]
            if not titles:
                continue

            summary = summarize_category(cat, titles)
            row = session.exec(select(CategorySummary).where(CategorySummary.category == cat)).first()

            if row:
                row.summary = summary
                row.updated_at = datetime.utcnow()
                session.add(row)
            else:
                session.add(CategorySummary(category=cat, summary=summary))

        session.commit()
        summary_status = "Summaries updated"
    except Exception:
        # Don’t break ingestion if OpenAI isn’t configured yet
        summary_status = "Summaries skipped (check OPENAI_API_KEY)"

    if x_status:
        msg = (
            f"Ingested {inserted_reddit} Reddit + {inserted_x} X posts • "
            f"{summary_status} • {x_status}"
        )
    else:
        msg = f"Ingested {inserted_reddit} Reddit + {inserted_x} X posts • {summary_status}"
    msg_param = quote_plus(msg)
    redirect_url = f"/dashboard?msg={msg_param}"
    if len(topic_list) == 1:
        redirect_url += f"&category={quote_plus(topic_list[0].lower())}"
    return RedirectResponse(redirect_url, status_code=302)


@app.get("/billing/checkout")
def billing_checkout(request: Request, session: Session = Depends(get_session)):
    """
    Stripe checkout. (Webhook activation still TBD)
    """
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    if not settings.stripe_secret_key or not settings.stripe_price_id:
        return RedirectResponse("/dashboard?msg=Stripe+not+configured", status_code=302)

    url = create_checkout_session(
        customer_email=user.email,
        success_url=f"{settings.base_url}/billing/success",
        cancel_url=f"{settings.base_url}/pricing",
    )
    return RedirectResponse(url, status_code=303)


@app.get("/billing/success")
def billing_success():
    return RedirectResponse(
        "/dashboard?msg=Payment+received.+Webhook+activation+coming+next",
        status_code=302,
    )
