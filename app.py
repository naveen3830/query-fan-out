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

st.sidebar.header("🛠️ Configuration & Setup")

with st.sidebar.expander(" How to get a Gemini API Key?"):
    st.markdown("""
    1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
    2. Sign in with your Google account.
    3. Click **Create API Key** and copy it.
    4. Paste the key in the field above.
    """)

gemini_key = st.sidebar.text_input(" Gemini API Key", type="password")
user_query = st.sidebar.text_area("Enter your query", "what is quantum key distribution?", height=120)
mode = st.sidebar.radio("🔬 Analysis Mode", ["Simple Analysis", "Deep Analysis"])

st.sidebar.markdown("---")

if gemini_key:
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.5-pro") # can use gemini-2.5-flash

else:
    st.error("Please enter your Gemini API Key to proceed.")
    st.stop()

def CONTENT_GAP_QUERY_PROMPT(q, mode):
    num_queries = 10 if mode == "Simple Analysis" else 20
    query_count_instruction = f"Generate exactly {num_queries} queries."

    return f"""Your goal is to act as a research strategist. Given a topic, you will generate a set of sophisticated and diverse web search queries. These queries are for an automated research tool that will synthesize the findings.

Original Topic: "{q}"

**Instructions:**
1.  **Generate Diverse Queries:** Create a set of queries that break down the original topic into its most important, distinct components.
2.  **Number of Queries:** {query_count_instruction}
3.  **Avoid Redundancy:** Do not generate multiple similar queries. Each query must target a unique angle or sub-topic to ensure comprehensive coverage.
4.  **Cover Different Facets:** The set of queries should cover a range of aspects, such as:
    -   Core definitions and foundational concepts ("what is...").
    -   Underlying mechanisms or technical processes ("how does... work").
    -   Practical applications and real-world use cases.
    -   Common challenges, limitations, or problems.
    -   Comparisons of internal components or methodologies (e.g., "quantum key distribution protocols comparison," NOT "Product X vs Competitor Y").
5.  **Categorize Each Query:** For each generated query, you must also provide its type and search intent as specified in the JSON format below.

**IMPORTANT CONSTRAINT:** The goal is to deepen the content on the primary topic itself, not to create competitor comparison articles. Avoid queries that compare the topic with external brands or competitors.

**Output Format:**
Return a single, valid JSON object. Do not add any text before or after the JSON object. The JSON must adhere to this exact structure:
{{
    "analysis_details": {{
        "target_query_count": {num_queries},
        "reasoning_for_count": "The number of queries is based on the selected '{mode}' to ensure comprehensive topic coverage by breaking it down into distinct facets.",
        "analysis_focus": "To create a diverse set of queries for comprehensive research, covering foundational concepts, technical details, applications, and challenges."
    }},
    "content_gap_queries": [
        {{
            "query": "Example query about a specific aspect of the main topic.",
            "type": "question_based",
            "search_intent": "informational",
            "gap_potential": "high",
            "reasoning": "This query targets a fundamental aspect of the topic that is essential for a complete understanding."
        }}
    ]
}}
"""

def generate_content_gap_queries(query, mode):
    prompt = CONTENT_GAP_QUERY_PROMPT(query, mode)
    try:
        response = model.generate_content(prompt)
        json_text = response.text.strip()
        
        if json_text.startswith("```json"):
            json_text = json_text[7:]
        if json_text.endswith("```"):
            json_text = json_text[:-3]
        json_text = json_text.strip()

        data = json.loads(json_text)
        analysis_details = data.get("analysis_details", {})
        generated_queries = data.get("content_gap_queries", [])

        st.session_state.analysis_details = analysis_details
        st.session_state.all_queries = generated_queries

        return generated_queries
    except json.JSONDecodeError as e:
        st.error(f"🔴 Failed to parse response as JSON: {e}")
        st.text("Raw response:")
        st.code(json_text if 'json_text' in locals() else "N/A", language='json')
        return None
    except Exception as e:
        st.error(f"🔴 Error during query generation: {e}")
        return None

def scrape_content(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
        
        text = soup.get_text(separator=' ', strip=True)
        
        return text[:5000] if len(text) > 5000 else text
    except Exception as e:
        return f"Error scraping {url}: {str(e)}"

def analyze_content_gaps_batch(queries_batch, scraped_contents):
    if not scraped_contents:
        return None
    
    content_summary = "\n\n".join([f"URL {i+1} Content Snippet:\n{content[:1000]}..." 
                                   for i, content in enumerate(scraped_contents) if content])
    
    queries_text = "\n".join([f"- {q['query']}" for q in queries_batch])
    
    analysis_prompt = f"""
    Analyze the following scraped content against this list of queries. The goal is to find what's missing from the content.

    QUERIES TO ANALYZE:
    {queries_text}

    SCRAPED CONTENT:
    {content_summary}

    For each query, perform the following analysis:
    1. Coverage Score (0-10): A score of 0 means the query is not addressed at all. A score of 10 means it is covered completely.
    2. Gaps Identified: Be specific and actionable. Instead of a generic 'information is missing', describe the missing details precisely. For example: "Lacks a step-by-step guide for implementation", "Does not explain the underlying security protocols", or "No mention of pricing or cost implications".
    3. Optimization Opportunities: Suggest concrete actions to fill the identified gaps. For example: "Add a new H2 section titled 'How to set up X'", "Create a table comparing the different pricing tiers".

    Return the analysis in a valid JSON format only, without any other text.
    {{
        "batch_analysis": [
            {{
                "query": "query text",
                "coverage_score": 7,
                "gaps_identified": ["The content mentions feature X but doesn't explain how it works.", "The practical benefits for small businesses are not detailed."],
                "optimization_opportunities": ["Add a 'How it Works' subsection with a diagram.", "Include a case study or example focused on small business use cases."],
                "competitive_potential": "high"
            }}
        ],
        "overall_insights": {{
            "strongest_areas": ["General overview of the topic", "Definition of key terms"],
            "biggest_gaps": ["Practical implementation guides", "Advanced use cases"],
            "quick_wins": ["Add a FAQ section to address common questions.", "Include a summary table at the beginning."]
        }}
    }}
    """
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(analysis_prompt)
            raw_text = response.text.strip()
            
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if not match:
                raise ValueError("No valid JSON object found in the model's response.")
            
            json_text = match.group(0)
            
            return json.loads(json_text)

        except (json.JSONDecodeError, ValueError) as e:
            st.warning(f"Batch analysis failed on attempt {attempt + 1}/{max_retries}. Retrying... Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2) 
            else:
                st.error(f"Error analyzing batch after {max_retries} attempts. This batch will be skipped.")
                st.code(raw_text, language='text')
                return None
        except Exception as e:
            st.error(f"An unexpected API error occurred during batch analysis: {e}")
            return None

    return None

if 'queries_generated' not in st.session_state:
    st.session_state.queries_generated = False
if 'generated_queries' not in st.session_state:
    st.session_state.generated_queries = []
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = []

if st.sidebar.button("🚀 Generate & Analyze"):
    with st.spinner("Generating diverse search queries..."):
        queries = generate_content_gap_queries(user_query, mode)
    
    if queries:
        st.session_state.generated_queries = queries
        st.session_state.queries_generated = True
        st.session_state.analysis_results = []

if st.session_state.queries_generated and st.session_state.generated_queries:
    if 'analysis_details' in st.session_state:
        details = st.session_state.analysis_details
        st.success(f"✅ Generated {details.get('target_query_count', len(st.session_state.generated_queries))} queries")
        st.info(f"📊 Reasoning: {details.get('reasoning_for_count', 'N/A')}")
    
    st.subheader("📝 Generated Queries for Comprehensive Research")
    queries_df = pd.DataFrame(st.session_state.generated_queries)
    st.dataframe(queries_df, use_container_width=True)
    
    st.subheader("🌐 Content Scraping & Analysis")
    
    url_input_method = st.radio("Choose URL input method:", ["Single URL", "Multiple URLs"])
    
    if url_input_method == "Single URL":
        single_url = st.text_input(
            "Enter URL to scrape and analyze:",
            placeholder="https://example.com",
            key="single_url_input"
        )
        urls_to_process = [single_url] if single_url.strip() else []
    else:
        urls_input = st.text_area(
            "Enter URLs to scrape and analyze (one per line):",
            placeholder="https://example1.com\nhttps://example2.com",
            height=100,
            key="multiple_urls_input"
        )
        urls_to_process = [url.strip() for url in urls_input.split('\n') if url.strip()]
    
    if st.button("🔍 Scrape & Analyze Content", key="scrape_analyze_btn"):
        if urls_to_process:
            st.session_state.urls_to_analyze = urls_to_process
            
            scraped_contents = []
            progress_bar = st.progress(0, text="Scraping URLs...")
            
            for i, url in enumerate(urls_to_process):
                with st.spinner(f"Scraping {url}..."):
                    content = scrape_content(url)
                    scraped_contents.append(content)
                progress_bar.progress((i + 1) / len(urls_to_process), text=f"Scraped {url}")
            
            st.success(f"✅ Scraped {len(urls_to_process)} URLs")
            
            st.session_state.scraped_contents = scraped_contents
            
            batch_size = 10
            queries = st.session_state.generated_queries
            num_batches = math.ceil(len(queries) / batch_size)
            
            all_analysis_results = []
            
            analysis_progress = st.progress(0, text="Starting analysis...")
            for batch_num in range(num_batches):
                start_idx = batch_num * batch_size
                end_idx = min((batch_num + 1) * batch_size, len(queries))
                batch_queries = queries[start_idx:end_idx]
                
                analysis_progress.progress(batch_num / num_batches, text=f"Analyzing batch {batch_num + 1}/{num_batches}...")
                
                with st.spinner(f"Analyzing batch {batch_num + 1}/{num_batches} ({len(batch_queries)} queries)..."):
                    batch_results = analyze_content_gaps_batch(batch_queries, scraped_contents)
                    if batch_results:
                        all_analysis_results.append(batch_results)
                
                if batch_num < num_batches - 1:
                    time.sleep(1)
            
            analysis_progress.progress(1.0, text="Analysis complete!")
            st.session_state.analysis_results = all_analysis_results
            
        else:
            st.warning("Please enter at least one URL to analyze.")

if st.session_state.analysis_results:
    st.subheader("📊 Content Gap Analysis Results")
    
    all_query_analyses = []
    for batch_result in st.session_state.analysis_results:
        all_query_analyses.extend(batch_result.get('batch_analysis', []))
    
    # Remove Competitive Potential from analyses for display/export
    for analysis in all_query_analyses:
        if 'competitive_potential' in analysis:
            del analysis['competitive_potential']
    
    # Display the table first
    results_df = pd.DataFrame(all_query_analyses)
    st.dataframe(results_df, use_container_width=True)
    
    # Single expander for all details
    with st.expander("Show Detailed Analysis for All Queries"):
        for i, analysis in enumerate(all_query_analyses):
            st.markdown(f"### Query {i+1}: {analysis.get('query', 'N/A')}")
            st.markdown(f"**Coverage Score:** {analysis.get('coverage_score', 'N/A')}/10")
            st.markdown("**Gaps Identified:**")
            for gap in analysis.get('gaps_identified', []):
                st.write(f"- {gap}")
            st.markdown("**Optimization Opportunities:**")
            for opp in analysis.get('optimization_opportunities', []):
                st.write(f"- {opp}")
            st.markdown("---")
    
    # CSV download button (single click)
    csv_data = results_df.to_csv(index=False)
    st.download_button(
        label="💾 Download Analysis Results as CSV",
        data=csv_data,
        file_name="content_gap_analysis_results.csv",
        mime="text/csv"
    )

if st.sidebar.checkbox("Show Debug Info"):
    st.sidebar.subheader("Debug Information")
    if 'analysis_details' in st.session_state:
        st.sidebar.json(st.session_state.analysis_details)
    if 'all_queries' in st.session_state:
        st.sidebar.write(f"Total queries generated: {len(st.session_state.all_queries)}")