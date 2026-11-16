import pandas as pd

from utils.data_summary import generate_dataset_summary
from graph.workflow import business_workflow


# Sample business dataset
data = {
    "Product": ["Laptop", "Mobile", "Laptop", "Tablet", "Mobile"],
    "City": ["Pune", "Mumbai", "Delhi", "Pune", "Mumbai"],
    "Sales": [50000, 30000, 60000, 20000, 40000],
    "Orders": [5, 3, 6, 2, 4]
}

df = pd.DataFrame(data)

# Generate dataset summary
dataset_summary = generate_dataset_summary(df)

# User question
question = "Which city has the highest sales?"

# Run LangGraph workflow
result = business_workflow.invoke({
    "dataset_summary": dataset_summary,
    "user_question": question,
    "analysis_result": "",
    "business_insights": ""
})

print("\nDATA ANALYST FINDINGS:")
print(result["analysis_result"])

print("\nBUSINESS INSIGHTS:")
print(result["business_insights"])