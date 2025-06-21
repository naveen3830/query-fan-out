import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import requests
from bs4 import BeautifulSoup
import hashlib
import os
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
st.set_page_config(page_title="Qforia Content Optimizer", layout="wide")
st.title("💡 Qforia: Content Gap Analysis via Query Fan-Out")
st.markdown("A two-step tool to align your content with the underlying intent of a search query.")

if 'search_plan' not in st.session_state:
    st.session_state.search_plan = None
if 'current_query_hash' not in st.session_state:
    st.session_state.current_query_hash = None
if 'gemini_configured' not in st.session_state:
    st.session_state.gemini_configured = False

st.sidebar.header("Configuration")
gemini_key = st.sidebar.text_input("Enter your Gemini API Key", type="password", help="Get Your Key from Google Cloud Console.")
user_query = st.sidebar.text_area("Enter your target query or prompt", "How does OT security impact manufacturing?", height=100)

def get_query_hash(query):
    """Create a hash of the query to detect changes"""
    return hashlib.md5(query.encode()).hexdigest()

current_hash = get_query_hash(user_query)
if st.session_state.current_query_hash != current_hash:
    # Query has changed, reset the search plan
    st.session_state.search_plan = None
    st.session_state.current_query_hash = current_hash
def configure_gemini(api_key):
    """Configure Gemini model"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash-latest")
        st.session_state.gemini_configured = True
        return model
    except Exception as e:
        st.error(f"Failed to configure Gemini: {e}")
        st.session_state.gemini_configured = False
        return None

model = None
if gemini_key:
    model = configure_gemini(gemini_key)
    if not model:
        st.error("Gemini model could not be initialized. Please check your API key.")
        st.stop()
else:
    st.info("Please enter your Gemini API Key in the sidebar to begin.")
    st.stop()

def create_search_plan_prompt(user_query):
    """Creates a prompt to generate the Analysis and Parallel Search Queries."""
    return f"""
You are the "Orchestrator" component of a state-of-the-art generative search engine. Your mission is to deconstruct a complex user query into a plan for gathering facts.

**User's Original Query:** "{user_query}"

**Your Task:**
Generate a single, valid JSON object representing the search plan. This plan MUST contain two top-level keys: `query_analysis` and `parallel_search_queries`.

**1. `query_analysis` Object:**
- `primary_entities`: Identify the main subjects.
- `key_attributes_and_constraints`: Identify the critical properties and conditions.
- `underlying_user_intent`: Describe the user's ultimate goal in one sentence.

**2. `parallel_search_queries` Array (The Fan-Out):**
Design a list of atomic, fact-finding queries to be executed in parallel. Each query object should have:
- `query_id`: A unique identifier (e.g., "Q1", "Q2").
- `query_type`: The type of system this query targets (e.g., "Definitional", "Impact_Analysis", "Best_Practices", "Risk_Assessment", "Comparative").
- `query_string`: The precise, machine-readable query.
- `purpose`: A brief explanation of why this specific fact is needed.

Generate 8-12 diverse queries that comprehensively cover the user's information needs.

Your entire output must be only the JSON object, no additional text or formatting.
"""

def create_content_analysis_prompt(queries_df, blog_text, original_query):
    """Creates a prompt to compare a blog post against a set of queries."""
    queries_json = queries_df.to_json(orient='records', indent=2)
    return f"""
You are a world-class SEO Content Strategist and Editor. Your task is to analyze a blog post to see how well it answers a comprehensive set of underlying user questions related to the target query: "{original_query}"

**CONTEXT:**

**1. The Ideal Search Plan (Fan-Out Queries):**
Here is a JSON array of ideal questions a user implicitly has when they search for the target topic. An ideal piece of content should address most of these.
```json
{queries_json}
```

**2. The Blog Post Content:**
Here is the text content scraped from the blog post you need to analyze.

```
{blog_text[:15000]}
```

(Note: Content may be truncated for brevity)

**YOUR ANALYSIS & RECOMMENDATION TASK:**

Based on the provided content and the ideal search plan, provide a detailed analysis and actionable recommendations. Structure your response in clean Markdown with the following sections:

### 1. Overall Alignment Score
Give a score out of 10 for how well the current content satisfies the user's full intent as represented by the search queries. Provide a one-sentence justification.

### 2. Coverage Analysis (What the Blog Does Well)
List the query_ids from the search plan that the blog post answers effectively. For each query_id, briefly quote or reference the specific part of the blog text that satisfies the query.

### 3. Content Gap Analysis (Missed Opportunities)
List the query_ids from the search plan that the blog post answers poorly or completely misses. For each missed query, explain what information is missing.

### 4. Actionable Recommendations for Improvement
Provide specific, concrete suggestions to fill the identified gaps. Be prescriptive and actionable.

Example Good Recommendation: "To address Q5 and Q8, add a new H2 section titled 'Top 5 Security Risks in Manufacturing OT Environments' and include a bulleted list detailing threats like ransomware, insider threats, and supply chain vulnerabilities."

### 5. Content Quality Assessment
Comment on the overall quality, readability, and structure of the existing content.

Your entire output must be in Markdown format and be thorough in your analysis.
"""

def generate_from_gemini(prompt, is_json=True):
    """Generic function to call Gemini and handle responses."""
    try:
        if is_json:
            response = model.generate_content(
                prompt, 
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.3
                }
            )
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            return json.loads(response_text)
        else:
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.3}
            )
            return response.text
    except json.JSONDecodeError as e:
        st.error(f"🔴 JSON parsing error: {e}")
        if 'response' in locals():
            st.code(response.text, language="text")
        return None
    except Exception as e:
        st.error(f"🔴 An error occurred with the Gemini API: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            st.code(response.text, language="text")
        return None

def scrape_blog_content(url):
    """Scrapes and cleans the text content from a given blog URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "button"]):
            element.decompose()
        
        # Focus on main content areas
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup.body
        
        if main_content:
            text = main_content.get_text()
        else:
            text = soup.get_text()
        
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        lines = text.split('\n')
        cleaned_lines = [line for line in lines if len(line) > 20 or line.strip() == '']
        text = '\n'.join(cleaned_lines)
        
        if not text or len(text) < 100:
            return None, "The scraper could not find substantial readable text content on the page."
        
        return text, None
    except requests.exceptions.RequestException as e:
        return None, f"Failed to fetch the URL. Error: {e}"
    except Exception as e:
        return None, f"An error occurred while scraping: {e}"

st.header("Step 1: Generate the Search & Content Plan")
st.markdown("Enter a target query your customers use. We'll deconstruct it into the underlying questions they really have.")

# Show current query being analyzed
if user_query.strip():
    st.info(f"**Current Query:** {user_query}")

if st.button("Generate Search Plan 🚀", key="generate_plan"):
    if user_query.strip():
        # Force reset of search plan for new generation
        st.session_state.search_plan = None
        
        with st.spinner("🤖 Deconstructing query and building search plan..."):
            prompt = create_search_plan_prompt(user_query)
            plan = generate_from_gemini(prompt, is_json=True)
            
            if plan and isinstance(plan, dict):
                if 'query_analysis' in plan and 'parallel_search_queries' in plan:
                    st.session_state.search_plan = plan
                    st.success("✅ Search plan generated successfully!")
                else:
                    st.error("🔴 Invalid search plan structure received from API.")
            else:
                st.error("🔴 Failed to generate search plan. Please try again.")
    else:
        st.warning("⚠️ Please enter a target query.")

if st.session_state.search_plan:
    plan = st.session_state.search_plan
    
    with st.expander("View Deconstructed Query Analysis", expanded=False):
        analysis = plan.get("query_analysis", {})
        st.markdown(f"**Primary Entities:** {analysis.get('primary_entities', 'N/A')}")
        st.markdown(f"**Key Attributes & Constraints:** {analysis.get('key_attributes_and_constraints', 'N/A')}")
        st.markdown(f"**Underlying User Intent:** _{analysis.get('underlying_user_intent', 'N/A')}_")
    
    st.subheader("Ideal Content Plan (Fan-Out Queries)")
    queries = plan.get("parallel_search_queries", [])
    if queries:
        df = pd.DataFrame(queries)
        st.dataframe(df, use_container_width=True)
        st.success(f"✅ Generated {len(queries)} targeted queries for comprehensive content analysis.")
    else:
        st.warning("No search queries were generated.")

st.markdown("---")
st.header("Step 2: Analyze Your Content Against the Plan")
st.markdown("Now, paste the URL of your blog post to see how well it aligns with the ideal content plan.")

if st.session_state.search_plan:
    blog_url = st.text_input("Enter your blog post URL", "", key="blog_url")
    
    if st.button("Analyze My Content 🔬", key="analyze_content"):
        if not blog_url.strip():
            st.warning("⚠️ Please enter a valid URL.")
        elif not blog_url.startswith(('http://', 'https://')):
            st.warning("⚠️ Please enter a valid URL starting with http:// or https://")
        else:
            with st.spinner(f"🔍 Scraping content from {blog_url}..."):
                blog_text, error_msg = scrape_blog_content(blog_url)
            
            if error_msg:
                st.error(f"🔴 {error_msg}")
                st.markdown("**Troubleshooting tips:**")
                st.markdown("- Ensure the URL is accessible and doesn't require login")
                st.markdown("- Some sites block automated scraping")
                st.markdown("- Check if the URL is correct and loads in your browser")
            elif blog_text:
                st.success(f"✅ Content scraped successfully! ({len(blog_text)} characters)")
                
                with st.expander("Preview Scraped Content", expanded=False):
                    st.text_area("Content Preview", blog_text[:1000] + "..." if len(blog_text) > 1000 else blog_text, height=200)
                
                with st.spinner("🧠 Analyzing content gaps and providing recommendations..."):
                    queries_df = pd.DataFrame(st.session_state.search_plan.get("parallel_search_queries", []))
                    analysis_prompt = create_content_analysis_prompt(queries_df, blog_text, user_query)
                    recommendations = generate_from_gemini(analysis_prompt, is_json=False)
                
                if recommendations:
                    st.subheader("📊 Content Strategy Recommendations")
                    st.markdown(recommendations)
                else:
                    st.error("🔴 Failed to generate content analysis. Please try again.")
else:
    st.info("📝 Complete Step 1 above to enable content analysis.")

st.markdown("---")