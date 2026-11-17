
from utils.llm_client import get_llm


MAX_SUMMARY_CHARS = 5000
MAX_ANALYSIS_CHARS = 6000


def _response_text(response):
    content = getattr(response, "content", response)

    if isinstance(content, str):
        return content

    return str(content)


def generate_business_insights(dataset_summary, analysis_result):

    summary = str(dataset_summary or "")[:MAX_SUMMARY_CHARS]
    analysis = str(analysis_result or "")[:MAX_ANALYSIS_CHARS]

    if not analysis.strip():
        return (
            "Business insights could not be generated "
            "because the Data Analyst returned no findings."
        )

    prompt = f"""
You are a professional Business Analyst.

Analyze the dataset summary and Data Analyst findings.

DATASET SUMMARY:
{summary}

DATA ANALYST FINDINGS:
{analysis}

Provide concise, practical business insights using these sections:

1. Key Business Findings
2. Important Trends
3. Business Opportunities
4. Risks or Areas of Concern
5. Actionable Recommendations

Rules:
- Use only the information provided.
- Do not invent numbers or findings.
- Keep recommendations practical.
- Avoid repeating the same information.
- Use clear and simple business language.
"""

    try:
        response = get_llm().invoke(prompt)
        return _response_text(response)

    except Exception as exc:
        raise RuntimeError(
            f"Business Analyst LLM request failed: {exc}"
        ) from exc
