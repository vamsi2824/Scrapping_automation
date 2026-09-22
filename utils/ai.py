import os
import pandas as pd
from google import genai
from google.genai import types

def _get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

def stream_store_performance(df: pd.DataFrame):
    """Callidus Reconciliation AI performance summary."""
    client = _get_gemini_client()
    if not client:
        yield "Error: GEMINI_API_KEY missing from .env."
        return

    if 'compmrc' not in df.columns:
        yield "Missing column 'compmrc' in dataset."
        return

    group_col = 'marketid' if 'marketid' in df.columns else 'Store Name'
    if group_col not in df.columns:
        yield f"Missing grouping column '{group_col}'."
        return

    summary = df.groupby(group_col)['compmrc'].sum().reset_index()
    summary = summary.sort_values(by='compmrc', ascending=False)
    
    total_rev = summary['compmrc'].sum()
    top_entry = summary.iloc[0]
    bottom_entry = summary.iloc[-1]
    top_pct = (top_entry['compmrc'] / total_rev * 100) if total_rev else 0

    top_3_str = ", ".join([f"{r[group_col]} (${r['compmrc']:,.2f})" for _, r in summary.head(3).iterrows()])
    bottom_str = f"{bottom_entry[group_col]} (${bottom_entry['compmrc']:,.2f})"

    brief_data = (
        f"Total Revenue: ${total_rev:,.2f}\n"
        f"Top Performers: {top_3_str}\n"
        f"Primary Driver: {top_entry[group_col]} accounts for {top_pct:.1f}% of total commission\n"
        f"Lowest Performer: {bottom_str}\n"
        f"Total Active {group_col.title()}s: {len(summary)}"
    )

    prompt = f"""
    You are an executive financial and operations director reviewing reconciliation results.
    Financial Summary:
    {brief_data}

    Write a cohesive executive summary consisting of exactly 4 to 5 complete, professional sentences:
    - Sentence 1: Total commission generated and the primary market driving the bulk of revenue.
    - Sentence 2: Secondary top performers and overall concentration of commission across key locations.
    - Sentence 3: Underperforming locations and the disparity between the top and bottom tiers.
    - Sentence 4: Key operational risk or efficiency bottleneck indicated by this distribution.
    - Sentence 5: Strategic recommendation to balance performance across active markets.

    Requirements:
    - Write full, articulate sentences.
    - Do not output internal thoughts, notes, markdown headings, or bullet fragments.
    - Output only the final paragraph directly.
    """

    config = types.GenerateContentConfig(max_output_tokens=1000, temperature=0.2)
    
    # Priority queue: Attempt beta models first, but guarantee execution using stable production models
    fallback_models = [
        'gemini-3.5-flash-lite', 
        'gemini-3.6-flash', 
        'gemini-3.8-flash',
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-1.5-flash'
    ]

    last_error = "Unknown Error"
    for model_name in fallback_models:
        try:
            response = client.models.generate_content_stream(
                model=model_name,
                contents=prompt,
                config=config
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
            return
        except Exception as e:
            # Capture the error and silently proceed to the next fallback model
            last_error = str(e)
            continue

    # If the script breaks out of the loop, every single model failed.
    # Expose the exact API response so it can be debugged immediately.
    yield f"Analysis failed: Exhausted all fallback models. Last API Error: {last_error}"


def stream_metro_kpi_performance(df: pd.DataFrame):
    """Metro KPI AI performance summary."""
    client = _get_gemini_client()
    if not client:
        yield "Error: GEMINI_API_KEY missing from .env."
        return

    required_cols = ['Store ID', 'Boxes', 'Acc $', 'PPD', 'QPAY']
    if not all(col in df.columns for col in required_cols):
        yield "Missing required columns for Metro KPI analysis."
        return

    summary = df.groupby('Store ID').agg({
        'Boxes': 'sum', 
        'Acc $': 'sum', 
        'PPD': 'sum', 
        'QPAY': 'sum'
    }).reset_index()
    
    if len(summary) == 0:
        yield "No data available to analyze."
        return

    summary = summary.sort_values(by='Boxes', ascending=False)
    total_boxes = summary['Boxes'].sum()
    total_acc = summary['Acc $'].sum()
    total_ppd = summary['PPD'].sum()
    total_qpay = summary['QPAY'].sum()
    overall_conv = (total_ppd / total_qpay * 100) if total_qpay > 0 else 0

    top_vol_store = summary.iloc[0]
    bottom_vol_store = summary.iloc[-1]
    
    summary_acc = summary.sort_values(by='Acc $', ascending=False)
    top_acc_store = summary_acc.iloc[0]

    brief_data = (
        f"Total Boxes (Volume): {total_boxes:,.0f}\n"
        f"Total Accessory Rev: ${total_acc:,.2f}\n"
        f"Overall Conversion: {overall_conv:.1f}%\n"
        f"Top Volume Store: {top_vol_store['Store ID']} ({top_vol_store['Boxes']} boxes)\n"
        f"Top Accessory Store: {top_acc_store['Store ID']} (${top_acc_store['Acc $']:,.2f})\n"
        f"Lowest Volume Store: {bottom_vol_store['Store ID']} ({bottom_vol_store['Boxes']} boxes)\n"
        f"Total Active Stores: {len(summary)}"
    )

    prompt = f"""
    You are an executive operations director reviewing daily Metro KPI results.
    Financial & Volume Summary:
    {brief_data}

    Write a cohesive executive summary consisting of exactly 4 to 5 complete, professional sentences:
    - Sentence 1: Summarize the overall box volume, accessory revenue, and network conversion rate.
    - Sentence 2: Identify the top performing locations driving volume and accessory attachments.
    - Sentence 3: Highlight the underperforming tier and the gap between them and the leaders.
    - Sentence 4: Note a specific operational bottleneck or opportunity.
    - Sentence 5: Provide a single strategic recommendation for store-level coaching.

    Requirements:
    - Write full, articulate sentences.
    - Do not output internal thoughts, notes, markdown headings, or bullet fragments.
    - Output only the final paragraph directly.
    """

    config = types.GenerateContentConfig(max_output_tokens=1000, temperature=0.2)
    
    fallback_models = [
        'gemini-3.5-flash-lite', 
        'gemini-3.6-flash', 
        'gemini-3.8-flash',
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-1.5-flash'
    ]

    last_error = "Unknown Error"
    for model_name in fallback_models:
        try:
            response = client.models.generate_content_stream(
                model=model_name,
                contents=prompt,
                config=config
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
            return
        except Exception as e:
            last_error = str(e)
            continue

    yield f"Analysis failed: Exhausted all fallback models. Last API Error: {last_error}"