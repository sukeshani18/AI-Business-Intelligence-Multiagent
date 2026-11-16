
from typing import TypedDict

import pandas as pd

from langgraph.graph import StateGraph, END

from agents.data_analyst import analyze_dataset
from agents.business_insight import generate_business_insights
from utils.data_summary import generate_dataset_summary


# =====================================================
# 1. WORKFLOW STATE
# =====================================================

class BusinessState(TypedDict):

    df: pd.DataFrame
    user_question: str

    dataset_summary: str
    analysis_result: str
    business_insights: str


# =====================================================
# 2. DATA ANALYST NODE
# =====================================================

def analyst_node(state: BusinessState):

    df = state["df"]
    question = state["user_question"]

    # Generate dataset summary
    dataset_summary = generate_dataset_summary(df)

    # Analyze user question
    analysis_result = analyze_dataset(
        df,
        question
    )

    return {
        "dataset_summary": dataset_summary,
        "analysis_result": analysis_result
    }


# =====================================================
# 3. BUSINESS INSIGHT NODE
# =====================================================

def insight_node(state: BusinessState):

    insights = generate_business_insights(
        state["dataset_summary"],
        state["analysis_result"]
    )

    return {
        "business_insights": insights
    }


# =====================================================
# 4. BUILD LANGGRAPH WORKFLOW
# =====================================================

workflow = StateGraph(BusinessState)

workflow.add_node(
    "analyst",
    analyst_node
)

workflow.add_node(
    "business_insight",
    insight_node
)

workflow.set_entry_point("analyst")

workflow.add_edge(
    "analyst",
    "business_insight"
)

workflow.add_edge(
    "business_insight",
    END
)


# Compile workflow
business_workflow = workflow.compile()
