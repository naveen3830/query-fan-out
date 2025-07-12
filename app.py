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
    model = genai.GenerativeModel("gemini-2.5-flash")
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
            f"Focus on variations that expand on the core topic. "
            f"Include long-tail variations, question-based queries, and related search intents."
        )
    else:  # Deep Analysis
        num_queries_instruction = (
            f"Analyze the user's query: \"{q}\" for comprehensive content gap analysis. "
            f"Generate **at least {min_queries_complex}** queries for deep content analysis. "
            f"Include semantic variations, user journey stages, related topics, and technical details. "
            f"Consider informational, transactional, and navigational search intents."
        )

    # CHANGED: I've updated the instructions to prevent competitor-focused queries.
    return (
        f"You are a content strategy assistant generating queries to help deepen and expand content on a specific topic.\n"
        f"Original topic: \"{q}\". Analysis mode: \"{mode}\".\n\n"
        f"**Task: Determine an optimal number of queries and generate them for an in-depth content analysis.**\n"
        f"{num_queries_instruction}\n\n"
        f"Each query should help identify potential content gaps by covering:\n"
        f"1. Semantic Variations - Different ways to express the same intent.\n"
        f"2. Related Questions - What users commonly ask about this topic.\n"
        f"3. Long-tail Keywords - Specific, detailed queries that reveal user needs.\n"
        f"4. Feature/Aspect Queries - Queries that dive into specific features, components, or use cases of the primary topic.\n"
        f"5. Problem/Solution Queries - Queries focused on the problems the topic solves.\n\n"
        f"**IMPORTANT CONSTRAINT:** Avoid generating queries that compare the primary topic with external competitors (e.g., avoid queries like \"Product X vs Competitor Y\"). The goal is to deepen the content on the primary topic itself, not to create competitor comparison articles.\n\n"
        f"Return valid JSON in this format:\n"
        f"{{\n"
        f"  \"analysis_details\": {{\n"
        f"    \"target_query_count\": 12,\n"
        f"    \"reasoning_for_count\": \"Explanation of why this number was chosen based on the topic's complexity\",\n"
        f"    \"analysis_focus\": \"Deepening content on the primary topic and identifying missed sub-topics.\"\n"
        f"  }},\n"
        f"  \"content_gap_queries\": [\n"
        f"    {{\n"
        f"      \"query\": \"Example query about the primary topic\",\n"
        f"      \"type\": \"long_tail_keyword\",\n"
        f"      \"search_intent\": \"informational\",\n"
        f"      \"gap_potential\": \"high\",\n"
        f"      \"reasoning\": \"This query helps to check for depth in a specific area of the main topic.\"\n"
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
    
    # --- NEW: Robust parsing with retry logic ---
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(analysis_prompt)
            raw_text = response.text.strip()
            
            # 1. More Aggressive JSON Cleaning: Find the first '{' and last '}'
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if not match:
                # This error is raised if no JSON-like structure is found at all
                raise ValueError("No valid JSON object found in the model's response.")
            
            json_text = match.group(0)
            
            # 2. Attempt to parse the cleaned text
            return json.loads(json_text)

        except (json.JSONDecodeError, ValueError) as e:
            st.warning(f"Batch analysis failed on attempt {attempt + 1}/{max_retries}. Retrying... Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait for 2 seconds before retrying
            else:
                st.error(f"Error analyzing batch after {max_retries} attempts. This batch will be skipped.")
                # For debugging, show the faulty text that could not be parsed
                st.text("Raw response that caused the final error:")
                st.code(raw_text, language='text')
                return None  # Return None after all retries have failed
        except Exception as e:
            # Catch any other unexpected errors from the API call itself
            st.error(f"An unexpected API error occurred during batch analysis: {e}")
            return None # Stop trying on other API errors

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