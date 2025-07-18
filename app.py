import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse
import math

st.set_page_config(page_title="Content Gap Analyzer", layout="wide")
st.title("🔍 Query-fan-out simulator & Content Analysis")
st.markdown("This tool generates strategic research queries and analyzes multiple URLs to find content gaps, suggesting the best page to optimize for each topic.")

st.sidebar.header("🛠️ Configuration & Setup")

with st.sidebar.expander("📖 How to get a Gemini API Key?"):
    st.markdown("""
    1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
    2. Sign in with your Google account.
    3. Click **Create API Key** and copy it.
    4. Paste the key in the field below.
    """)

if 'gemini_api_key' not in st.session_state:
    st.session_state.gemini_api_key = ''

st.session_state.gemini_api_key = st.sidebar.text_input("🔑 Gemini API Key", type="password", value=st.session_state.gemini_api_key)
user_query = st.sidebar.text_area("Enter your core topic or keyword", "what is quantum key distribution?", height=120)
mode = st.sidebar.radio("🔬 Analysis Mode", ["Simple Analysis", "Deep Analysis"], help="Deep Analysis generates more queries for a more thorough investigation.")

st.sidebar.markdown("---")
st.sidebar.subheader("Advanced Scraping Settings")
char_limit = st.sidebar.slider(
    "Scraping Character Limit per URL",
    min_value=1000,
    max_value=20000,
    value=20000,
    step=1000,
    help="Set the maximum number of characters to scrape from each URL. A higher limit provides more context but may increase processing time and cost."
)
st.sidebar.markdown("---")

if st.session_state.gemini_api_key:
    try:
        genai.configure(api_key=st.session_state.gemini_api_key)

        model = genai.GenerativeModel("gemini-2.5-pro")
    except Exception as e:
        st.error(f"Failed to configure Gemini API: {e}")
        st.stop()
else:
    st.warning("Please enter your Gemini API Key in the sidebar to begin.")
    st.stop()

def CONTENT_GAP_QUERY_PROMPT(q, mode):
    num_queries = 10 if mode == "Simple Analysis" else 20
    query_count_instruction = f"Generate exactly {num_queries} queries."

    return f"""
    Your goal is to act as a research strategist. Given a topic, you will generate a set of sophisticated and diverse web search queries. These queries are for an automated research tool that will synthesize the findings.

    Original Topic: "{q}"

    **Instructions:**
    1.  **Generate Diverse Queries:** Create a set of queries that break down the original topic into its most important, distinct components.
    2.  **Number of Queries:** {query_count_instruction}
    3.  **Avoid Redundancy:** Each query must target a unique angle or sub-topic.
    4.  **Cover Different Facets:** The queries should cover a range of aspects: foundational concepts, technical processes, applications, challenges, and internal comparisons (e.g., different protocols or methods).
    5.  **Categorize Each Query:** Provide a type and search intent for each query.

    **IMPORTANT CONSTRAINT:** The goal is to deepen content on the primary topic, not to create competitor comparison articles. Avoid queries that compare the topic with external brands or competitors.

    **Output Format:**
    Return a single, valid JSON object. Do not add any text before or after the JSON.
    {{
        "analysis_details": {{
            "target_query_count": {num_queries},
            "reasoning_for_count": "The number of queries is based on the selected '{mode}' to ensure comprehensive topic coverage.",
            "analysis_focus": "To create a diverse set of queries for comprehensive research, covering foundational concepts, technical details, applications, and challenges."
        }},
        "content_gap_queries": [
            {{
                "query": "Example query about a specific aspect of the main topic.",
                "type": "question_based",
                "search_intent": "informational"
            }}
        ]
    }}
    """

def generate_content_gap_queries(query, mode):
    """Calls the Gemini API to generate queries and handles response parsing."""
    prompt = CONTENT_GAP_QUERY_PROMPT(query, mode)
    try:
        response = model.generate_content(prompt)
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response.text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'(\{.*?\})', response.text, re.DOTALL)
        
        json_text = json_match.group(1)
        data = json.loads(json_text)
        
        st.session_state.analysis_details = data.get("analysis_details", {})
        return data.get("content_gap_queries", [])

    except (json.JSONDecodeError, AttributeError) as e:
        st.error(f"🔴 Failed to parse response as JSON. Error: {e}")
        st.text("Raw response from model:")
        st.code(response.text if 'response' in locals() else "N/A", language='text')
        return None
    except Exception as e:
        st.error(f"🔴 An unexpected error occurred during query generation: {e}")
        return None

def scrape_content(url, character_limit):
    """Scrapes and cleans text content from a URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            element.decompose()
        
        text = soup.get_text(separator=' ', strip=True)
        return {"url": url, "content": text[:character_limit]}
    
    except requests.exceptions.RequestException as e:
        st.warning(f"Could not scrape {url}: {e}")
        return {"url": url, "content": f"Error: Failed to retrieve content. {e}"}

def analyze_content_gaps_batch(queries_batch, scraped_data, character_limit):
    """Analyzes content gaps for a batch of queries against multiple URLs."""
    if not scraped_data: return None

    content_summary = "\n\n---\n\n".join(
        [f"CONTENT FROM: {item['url']}\n\n{item['content'][:2000]}..." for item in scraped_data if item['content']]
    )
    queries_text = "\n".join([f"- {q['query']}" for q in queries_batch])

    analysis_prompt = f"""
    You are an expert Content Gap Analyst. Your task is to analyze content from multiple URLs against a list of queries. The content provided was scraped up to the first {character_limit} characters.

    **URLs AND THEIR CONTENT SNIPPETS:**
    {content_summary}

    **RESEARCH QUERIES TO ANALYZE:**
    {queries_text}

    **INSTRUCTIONS:**
    For each query, evaluate how well it is covered by the content from **each** of the provided URLs. Return your analysis as a single, valid JSON object.

    - **coverage_score (0-10):** 0 means not addressed; 10 means fully covered.
    - **gap_description:** Be specific. Instead of "information is missing," say "Lacks a step-by-step guide for implementation."
    - **optimization_suggestion:** Give a concrete action, e.g., "Add a new H2 section titled 'How to set up X'."

    **JSON OUTPUT STRUCTURE:**
    {{
      "batch_analysis": [
        {{
          "query": "The text of the research query.",
          "analysis_per_url": [
            {{
              "url": "https://example.com/page-a",
              "coverage_score": 8,
              "gap_description": "The topic is mentioned, but lacks depth on technical aspects.",
              "optimization_suggestion": "Expand the section with more technical details and diagrams."
            }}
          ]
        }}
      ]
    }}
    """
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(analysis_prompt)
            raw_text = response.text.strip()
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if not match: raise ValueError("No valid JSON object found in model's response.")
            json_text = match.group(0)
            return json.loads(json_text)
        except (json.JSONDecodeError, ValueError) as e:
            st.warning(f"Analysis failed on attempt {attempt + 1}. Retrying... Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                st.error(f"Error analyzing batch after {max_retries} attempts. Skipping.")
                st.code(raw_text, language='text')
                return None
        except Exception as e:
            st.error(f"An unexpected API error during analysis: {e}")
            return None

def process_and_display_results(analysis_results):
    """Processes raw analysis data to create final DataFrames and display results."""
    st.header("📊 Content Gap Analysis Results", anchor=False)
    
    summary_results = []
    detailed_results_flat = []
    all_detailed_analyses = []

    for batch_result in analysis_results:
        for query_analysis in batch_result.get('batch_analysis', []):
            all_detailed_analyses.append(query_analysis)
            query_text = query_analysis.get('query')
            analysis_per_url = query_analysis.get('analysis_per_url', [])
            
            if not analysis_per_url: continue

            for url_detail in analysis_per_url:
                detailed_results_flat.append({
                    "Query": query_text,
                    "URL Analyzed": url_detail.get('url'),
                    "Coverage Score": url_detail.get('coverage_score', 0),
                    "Identified Gap": url_detail.get('gap_description', 'N/A'),
                    "Optimization Suggestion": url_detail.get('optimization_suggestion', 'N/A')
                })

            best_target = max(analysis_per_url, key=lambda x: x.get('coverage_score', 0))
            summary_results.append({
                "Query": query_text,
                "Target for Optimization": best_target.get('url'),
                "Highest Coverage Score": best_target.get('coverage_score', 0),
                "Identified Gap": best_target.get('gap_description', 'N/A'),
                "Optimization Suggestion": best_target.get('optimization_suggestion', 'N/A')
            })

    if not summary_results:
        st.warning("Analysis did not return any actionable results to display.")
        return

    st.subheader("Summary: Best Page to Optimize per Query", anchor=False)
    summary_df = pd.DataFrame(summary_results)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
    
    summary_csv = summary_df.to_csv(index=False).encode('utf-8')
    detailed_df = pd.DataFrame(detailed_results_flat)
    detailed_csv = detailed_df.to_csv(index=False).encode('utf-8')

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="💾 Download Summary Analysis (CSV)",
            data=summary_csv,
            file_name=f"content_gap_summary_{user_query.replace(' ','_')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col2:
        st.download_button(
            label="💾 Download Detailed Analysis (CSV)",
            data=detailed_csv,
            file_name=f"content_gap_detailed_{user_query.replace(' ','_')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with st.expander("🔬 Show Detailed Analysis (All URLs)"):
        for analysis in all_detailed_analyses:
            st.markdown(f"#### Query: {analysis.get('query', 'N/A')}")
            for url_detail in sorted(analysis.get('analysis_per_url', []), key=lambda x: x.get('coverage_score', 0), reverse=True):
                st.markdown(f"**URL:** `{url_detail.get('url')}`")
                score = url_detail.get('coverage_score', 'N/A')
                st.markdown(f"**Coverage Score:** **{score}** / 10")
                st.markdown(f"**Gap:** {url_detail.get('gap_description', 'N/A')}")
                st.markdown(f"**Suggestion:** {url_detail.get('optimization_suggestion', 'N/A')}")
                st.divider()

if 'queries_generated' not in st.session_state: st.session_state.queries_generated = False
if 'generated_queries' not in st.session_state: st.session_state.generated_queries = []
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = []

if st.sidebar.button("🚀 Generate Queries", use_container_width=True):
    with st.spinner("Generating diverse search queries..."):
        queries = generate_content_gap_queries(user_query, mode)
    
    if queries:
        st.session_state.generated_queries = queries
        st.session_state.queries_generated = True
        st.session_state.analysis_results = []
        st.success(f"✅ Generated {len(queries)} queries.")
        st.rerun()
    else:
        st.error("Failed to generate queries. Please check API key and try again.")

if st.session_state.queries_generated:
    st.header("📝 Generated Queries", anchor=False)
    st.dataframe(pd.DataFrame(st.session_state.generated_queries), use_container_width=True, hide_index=True)
    
    st.header("🌐 Enter URLs for Analysis", anchor=False)
    urls_input = st.text_area(
        "Enter URLs to analyze (one per line).",
        placeholder="https://example.com/topic-a\nhttps://example.com/related-topic-b",
        height=100,
        key="multiple_urls_input"
    )
    urls_to_process = [url.strip() for url in urls_input.split('\n') if url.strip() and url.startswith('http')]
    
    if st.button("🔍 Scrape & Analyze Content", key="scrape_analyze_btn", disabled=not urls_to_process, use_container_width=True):
        with st.status("Running Full Analysis...", expanded=True) as status:
            status.update(label=f"Step 1/3: Scraping content (up to {char_limit} chars/URL)...")
            scraped_data = [scrape_content(url, char_limit) for url in urls_to_process]
            time.sleep(1)
            
            status.update(label=f"Step 2/3: Analyzing content against {len(st.session_state.generated_queries)} queries...")
            queries = st.session_state.generated_queries
            batch_size = 5
            num_batches = math.ceil(len(queries) / batch_size)
            
            progress_bar = st.progress(0)
            all_analysis_results = []
            for i in range(num_batches):
                start_idx, end_idx = i * batch_size, (i + 1) * batch_size
                batch_queries = queries[start_idx:end_idx]
                
                status.update(label=f"Step 2/3: Analyzing batch {i + 1}/{num_batches}...")
                batch_results = analyze_content_gaps_batch(batch_queries, scraped_data, char_limit)
                if batch_results:
                    all_analysis_results.append(batch_results)
                
                progress_bar.progress((i + 1) / num_batches)
                time.sleep(2)

            st.session_state.analysis_results = all_analysis_results
            status.update(label="✅ Analysis Complete!", state="complete")
        st.rerun()

if st.session_state.analysis_results:
    process_and_display_results(st.session_state.analysis_results)

if st.sidebar.checkbox("Show Debug Info"):
    st.sidebar.subheader("Debug Information")
    with st.sidebar.expander("Session State"):
        st.json({k: v for k, v in st.session_state.to_dict().items() if k != 'gemini_api_key'})