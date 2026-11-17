
from typing import TypedDict

import pandas as pd
from langgraph.graph import StateGraph, END

from agents.data_analyst import analyze_dataset
from agents.business_insight import generate_business_insights
from utils.data_summary import generate_dataset_summary


class BusinessState(TypedDict, total=False):
    df: pd.DataFrame
    user_question: str
    dataset_summary: str
    analysis_result: str
    business_insights: str


def analyst_node(state):

    df = state["df"]
    question = state["user_question"]

    dataset_summary = generate_dataset_summary(df)

    analysis_result = analyze_dataset(df, question)

    return {
        "dataset_summary": dataset_summary,
        "analysis_result": analysis_result
    }


def insight_node(state):

    analysis = state.get("analysis_result", "")

    if not analysis or not str(analysis).strip():

        insights = (
            "Business insights could not be generated "
            "because no Data Analyst response was returned."
        )

    else:

        insights = generate_business_insights(
            state.get("dataset_summary", ""),
            analysis
        )

    return {
        "business_insights": insights
    }


workflow = StateGraph(BusinessState)

workflow.add_node("analyst", analyst_node)
workflow.add_node("business_insight", insight_node)

workflow.set_entry_point("analyst")

workflow.add_edge("analyst", "business_insight")
workflow.add_edge("business_insight", END)

business_workflow = workflow.compile()
