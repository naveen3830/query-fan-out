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

st.sidebar.header("Configuration")
gemini_key = st.sidebar.text_input("Gemini API Key", type="password")
user_query = st.sidebar.text_area("Enter your query", "what is quantum key encryption?", height=120)
mode = st.sidebar.radio("Analysis Mode", ["Simple Analysis", "Deep Analysis"])

if gemini_key:
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-1.5-flash-latest")
else:
    st.error("Please enter your Gemini API Key to proceed.")
    st.stop()

def CONTENT_GAP_QUERY_PROMPT(q, mode):
    min_queries_simple = 10
    min_queries_complex = 20
    
    if mode == "Simple Analysis":
        num_queries_instruction = (
            f"Analyze the user's query: \"{q}\" for content gap analysis. "
            f"Generate **at least {min_queries_simple}** queries that would help identify content gaps. "
            f"Focus on variations that competitors might rank for but current content might miss. "
            f"Include long-tail variations, question-based queries, and related search intents."
        )
    else:  # Deep Analysis
        num_queries_instruction = (
            f"Analyze the user's query: \"{q}\" for comprehensive content gap analysis. "
            f"Generate **at least {min_queries_complex}** queries for deep content analysis. "
            f"Include semantic variations, user journey stages, related topics, and competitive angles. "
            f"Consider informational, transactional, and navigational search intents."
        )

    return (
        f"You are generating queries for content gap analysis and competitive research.\n"
        f"Original query: \"{q}\". Analysis mode: \"{mode}\".\n\n"
        f"**Task: Determine optimal number of queries and generate them for content analysis.**\n"
        f"{num_queries_instruction}\n\n"
        f"Each query should help identify potential content gaps by covering:\n"
        f"1. Semantic Variations - Different ways to express the same intent\n"
        f"2. Related Questions - What users commonly ask about this topic\n"
        f"3. Long-tail Keywords - Specific, detailed queries\n"
        f"4. Comparison Queries - Competitive analysis angles\n"
        f"5. Problem-Solution Queries - Pain points and solutions\n"
        f"6. Feature-Specific Queries - Detailed aspects of the topic\n\n"
        f"Focus on queries that would reveal content opportunities when analyzing competitor content.\n"
        f"Avoid queries requiring real-time data or personal information.\n\n"
        f"Return valid JSON in this format:\n"
        f"{{\n"
        f"  \"analysis_details\": {{\n"
        f"    \"target_query_count\": 12,\n"
        f"    \"reasoning_for_count\": \"Explanation of why this number was chosen\",\n"
        f"    \"analysis_focus\": \"Content gap identification and competitive analysis\"\n"
        f"  }},\n"
        f"  \"content_gap_queries\": [\n"
        f"    {{\n"
        f"      \"query\": \"Example query\",\n"
        f"      \"type\": \"semantic_variation\",\n"
        f"      \"search_intent\": \"informational\",\n"
        f"      \"gap_potential\": \"high\",\n"
        f"      \"reasoning\": \"Why this query helps identify content gaps\"\n"
        f"    }}\n"
        f"  ]\n"
        f"}}"
    )
    
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
        st.text(json_text if 'json_text' in locals() else "N/A")
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
        
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text[:5000] if len(text) > 5000 else text
    except Exception as e:
        return f"Error scraping {url}: {str(e)}"

def analyze_content_gaps_batch(queries_batch, scraped_contents):
    if not scraped_contents:
        return None
    
    content_summary = "\n\n".join([f"URL {i+1} Content:\n{content[:1000]}..." 
                                for i, content in enumerate(scraped_contents) if content])
    
    queries_text = "\n".join([f"- {q['query']}" for q in queries_batch])
    
    analysis_prompt = f"""
    Analyze the following scraped content against these queries to identify content gaps:

    QUERIES TO ANALYZE:
    {queries_text}

    SCRAPED CONTENT:
    {content_summary}

    For each query, determine:
    1. Coverage Score (0-10): How well the content covers this query
    2. Content Gaps: What specific information is missing
    3. Optimization Opportunities: How to improve content for this query
    4. Competitive Advantage: Potential to outrank competitors

    Return JSON format:
    {{
        "batch_analysis": [
            {{
                "query": "query text",
                "coverage_score": 7,
                "gaps_identified": ["gap1", "gap2"],
                "optimization_opportunities": ["opportunity1", "opportunity2"],
                "competitive_potential": "high/medium/low"
            }}
        ],
        "overall_insights": {{
            "strongest_areas": ["area1", "area2"],
            "biggest_gaps": ["gap1", "gap2"],
            "quick_wins": ["win1", "win2"]
        }}
    }}
    """
    
    try:
        response = model.generate_content(analysis_prompt)
        json_text = response.text.strip()
        
        if json_text.startswith("```json"):
            json_text = json_text[7:]
        if json_text.endswith("```"):
            json_text = json_text[:-3]
        json_text = json_text.strip()
        
        return json.loads(json_text)
    except Exception as e:
        st.error(f"Error analyzing batch: {e}")
        return None

# Initialize session state
if 'queries_generated' not in st.session_state:
    st.session_state.queries_generated = False
if 'generated_queries' not in st.session_state:
    st.session_state.generated_queries = []
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = []

# Main execution
if st.sidebar.button("🚀 Generate & Analyze"):
    with st.spinner("Generating content gap queries..."):
        queries = generate_content_gap_queries(user_query, mode)
    
    if queries:
        st.session_state.generated_queries = queries
        st.session_state.queries_generated = True
        st.session_state.analysis_results = []  # Reset previous analysis results

# Display generated queries if they exist
if st.session_state.queries_generated and st.session_state.generated_queries:
    # Display generation details
    if hasattr(st.session_state, 'analysis_details'):
        details = st.session_state.analysis_details
        st.success(f"✅ Generated {details.get('target_query_count', len(st.session_state.generated_queries))} queries")
        st.info(f"📊 Reasoning: {details.get('reasoning_for_count', 'N/A')}")
    
    # Display generated queries
    st.subheader("📝 Generated Queries for Content Gap Analysis")
    queries_df = pd.DataFrame(st.session_state.generated_queries)
    st.dataframe(queries_df, use_container_width=True)
    
    # URL input for content scraping
    st.subheader("🌐 Content Scraping & Analysis")
    
    # URL input options
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
            placeholder="https://example1.com\nhttps://example2.com\nhttps://example3.com",
            height=100,
            key="multiple_urls_input"
        )
        urls_to_process = [url.strip() for url in urls_input.split('\n') if url.strip()]
    
    if st.button("🔍 Scrape & Analyze Content", key="scrape_analyze_btn"):
        if urls_to_process:
            # Store URLs in session state
            st.session_state.urls_to_analyze = urls_to_process
            
            # Scrape content
            scraped_contents = []
            progress_bar = st.progress(0)
            
            for i, url in enumerate(urls_to_process):
                with st.spinner(f"Scraping {url}..."):
                    content = scrape_content(url)
                    scraped_contents.append(content)
                progress_bar.progress((i + 1) / len(urls_to_process))
            
            st.success(f"✅ Scraped {len(urls_to_process)} URLs")
            
            # Store scraped content in session state
            st.session_state.scraped_contents = scraped_contents
            
            # Analyze in batches of 10 queries
            batch_size = 10
            queries = st.session_state.generated_queries
            num_batches = math.ceil(len(queries) / batch_size)
            
            all_analysis_results = []
            
            for batch_num in range(num_batches):
                start_idx = batch_num * batch_size
                end_idx = min((batch_num + 1) * batch_size, len(queries))
                batch_queries = queries[start_idx:end_idx]
                
                with st.spinner(f"Analyzing batch {batch_num + 1}/{num_batches} ({len(batch_queries)} queries)..."):
                    batch_results = analyze_content_gaps_batch(batch_queries, scraped_contents)
                    if batch_results:
                        all_analysis_results.append(batch_results)
                
                if batch_num < num_batches - 1:
                    time.sleep(1)
            
            st.session_state.analysis_results = all_analysis_results
            
        else:
            st.warning("Please enter at least one URL to analyze.")

if st.session_state.analysis_results:
    st.subheader("📊 Content Gap Analysis Results")
    
    all_query_analyses = []
    for batch_result in st.session_state.analysis_results:
        all_query_analyses.extend(batch_result.get('batch_analysis', []))
    
    results_df = pd.DataFrame(all_query_analyses)
    st.dataframe(results_df, use_container_width=True)
    
    st.subheader("💡 Key Insights")
    for i, batch_result in enumerate(st.session_state.analysis_results):
        if 'overall_insights' in batch_result:
            insights = batch_result['overall_insights']
            st.write(f"**Batch {i+1} Insights:**")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write("**Strongest Areas:**")
                for area in insights.get('strongest_areas', []):
                    st.write(f"• {area}")
            
            with col2:
                st.write("**Biggest Gaps:**")
                for gap in insights.get('biggest_gaps', []):
                    st.write(f"• {gap}")
            
            with col3:
                st.write("**Quick Wins:**")
                for win in insights.get('quick_wins', []):
                    st.write(f"• {win}")
            
            st.markdown("---")
    
    # Export option
    if st.button("📥 Export Results", key="export_btn"):
        results_json = {
            "original_query": user_query,
            "analysis_mode": mode,
            "generated_queries": st.session_state.generated_queries,
            "scraped_urls": st.session_state.get('urls_to_analyze', []),
            "analysis_results": st.session_state.analysis_results
        }
        
        st.download_button(
            label="💾 Download Analysis Results",
            data=json.dumps(results_json, indent=2),
            file_name=f"content_gap_analysis_{user_query[:30].replace(' ', '_')}.json",
            mime="application/json",
            key="download_btn"
        )

if st.sidebar.checkbox("Show Debug Info"):
    st.sidebar.subheader("Debug Information")
    if hasattr(st.session_state, 'analysis_details'):
        st.sidebar.json(st.session_state.analysis_details)
    if hasattr(st.session_state, 'all_queries'):
        st.sidebar.write(f"Total queries generated: {len(st.session_state.all_queries)}")