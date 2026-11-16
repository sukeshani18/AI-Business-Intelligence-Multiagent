
from utils.llm_client import get_llm


def generate_business_insights(dataset_summary, analysis_result):

    try:

        llm = get_llm()

        prompt = f"""
You are an experienced Business Strategy Consultant.

Your task is to convert data analysis findings into
practical business insights.

DATASET INFORMATION:
{dataset_summary}

DATA ANALYST FINDINGS:
{analysis_result}

YOUR TASK:

1. BUSINESS INTERPRETATION
   Explain what the findings mean for the business.

2. RISKS AND OPPORTUNITIES
   Identify important risks and potential opportunities
   supported by the available findings.

3. RECOMMENDED STRATEGIES
   Suggest 3 practical business strategies.

4. EXPECTED BENEFITS
   Explain how each strategy may help the business.

INSTRUCTIONS:

- Use simple and professional English.
- Base recommendations on the supplied findings.
- Never invent statistics or business facts.
- Clearly distinguish facts from suggestions.
- Avoid generic recommendations.
- Do not repeat the entire data analysis.
- Keep the response concise and actionable.

FORMAT:

### Business Interpretation

### Risks and Opportunities

### Recommended Strategies

### Expected Benefits
"""

        response = llm.invoke(prompt)

        return response.content

    except Exception as e:

        return f"Unable to generate business insights: {str(e)}"
