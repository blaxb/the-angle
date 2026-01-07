from openai import OpenAI
from .settings import settings

client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

def summarize_category(category: str, titles: list[str]) -> str:
    if not client:
        return "OpenAI key not configured."

    sample = "\n".join([f"- {t}" for t in titles[:30]])
    prompt = f"""
You are helping a journalist. Summarize what people are discussing in the category: {category}.
Use only the list of conversation titles. Output:

1) One-sentence summary
2) 5 bullet key angles journalists could write
3) 5 suggested headlines

Titles:
{sample}
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()


def summarize_post(title: str, comments: list[str] | None = None) -> str:
    if not client:
        return title

    comment_block = ""
    if comments:
        comment_block = "\n\nTop comments:\n" + "\n".join([f"- {c}" for c in comments[:6]])

    prompt = f"""
You are summarizing a Reddit conversation for a dashboard list.
Use the title and comments to create a concise, plain-language summary in one sentence (max 18 words).
Avoid quotes, numbering, and hashtags.

Title:
{title}
{comment_block}
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()
