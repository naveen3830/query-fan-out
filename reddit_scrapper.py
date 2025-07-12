import streamlit as st
import pandas as pd
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
import io
import time
from urllib.parse import urlparse
import math

st.set_page_config(
    page_title="Reddit URL Scraper",
    page_icon="🔍",
    layout="wide"
)

def get_reddit_html(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return None

def extract_reddit_details(html_content):
    if not html_content:
        return {
            'reddit_title': 'Error: Could not fetch',
            'reddit_posted_time': 'Error',
            'reddit_time_ago': 'Error',
            'reddit_comments_count': 'Error',
            'reddit_score': 'Error',
            'reddit_is_archived': 'Error'
        }
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    details = {
        'reddit_title': 'Not found',
        'reddit_posted_time': 'Not found',
        'reddit_time_ago': 'Not found',
        'reddit_comments_count': 'Not found',
        'reddit_score': 'Not found',
        'reddit_is_archived': 'No'
    }
    
    shreddit_post = soup.find('shreddit-post')
    
    if shreddit_post:
        if shreddit_post.get('post-title'):
            details['reddit_title'] = shreddit_post.get('post-title')
        
        if shreddit_post.get('created-timestamp'):
            timestamp = shreddit_post.get('created-timestamp')
            try:
                # Handle different timestamp formats
                if 'T' in timestamp:
                    # ISO format: 2023-10-03T19:03:52.606000+0000
                    clean_timestamp = timestamp.replace('Z', '+00:00')
                    if '+0000' in clean_timestamp:
                        clean_timestamp = clean_timestamp.replace('+0000', '+00:00')
                    
                    # Remove microseconds if present
                    if '.' in clean_timestamp:
                        base_time, rest = clean_timestamp.split('.')
                        timezone = '+00:00'
                        if '+' in rest:
                            timezone = '+' + rest.split('+')[1]
                        elif '-' in rest:
                            timezone = '-' + rest.split('-')[1]
                        clean_timestamp = base_time + timezone
                    
                    dt = datetime.fromisoformat(clean_timestamp)
                    dt = dt.replace(tzinfo=None)
                else:
                    # Unix timestamp
                    dt = datetime.fromtimestamp(float(timestamp))
                
                details['reddit_posted_time'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # Calculate time ago in Reddit format
                now = datetime.now()
                diff = now - dt
                
                total_seconds = diff.total_seconds()
                total_days = diff.days
                
                if total_days >= 365:
                    years = math.ceil(total_days / 365)
                    details['reddit_time_ago'] = f"{years} yr. ago"
                elif total_days >= 30:
                    months = math.ceil(total_days / 30)
                    details['reddit_time_ago'] = f"{months} mo. ago"
                elif total_days >= 1:
                    details['reddit_time_ago'] = f"{total_days} day{'s' if total_days > 1 else ''} ago"
                elif total_seconds >= 3600:
                    hours = int(total_seconds // 3600)
                    details['reddit_time_ago'] = f"{hours} hr. ago"
                elif total_seconds >= 60:
                    minutes = int(total_seconds // 60)
                    details['reddit_time_ago'] = f"{minutes} min. ago"
                else:
                    details['reddit_time_ago'] = "now"
                    
            except Exception:
                details['reddit_posted_time'] = 'Parse error'
                details['reddit_time_ago'] = 'Parse error'
        
        # Extract Comments Count
        if shreddit_post.get('comment-count'):
            details['reddit_comments_count'] = shreddit_post.get('comment-count')
        
        # Extract Score (Votes)
        if shreddit_post.get('score'):
            details['reddit_score'] = shreddit_post.get('score')
    
    # Check if post is archived or locked (robust check for both in the same span)
    status_span = soup.find('span', class_='flex flex-auto flex-col justify-center text-14 pl-sm')
    if status_span:
        text = status_span.get_text().lower()
        if 'archived post' in text or 'locked post' in text:
            details['reddit_is_archived'] = 'Yes'
    
    # Alternative method using regex if BeautifulSoup fails
    if details['reddit_title'] == 'Not found':
        regex_details = extract_with_regex(html_content)
        details.update(regex_details)
    
    return details

def extract_with_regex(html_content):
    """
    Fallback method using regex to extract details
    """
    details = {}
    
    # Extract title using regex
    title_match = re.search(r'post-title="([^"]*)"', html_content)
    if title_match:
        details['reddit_title'] = title_match.group(1)
    
    # Extract comments count
    comments_match = re.search(r'comment-count="([^"]*)"', html_content)
    if comments_match:
        details['reddit_comments_count'] = comments_match.group(1)
    
    # Extract score
    score_match = re.search(r'score="([^"]*)"', html_content)
    if score_match:
        details['reddit_score'] = score_match.group(1)
    
    # Check archived status
    if 'Archived post.' in html_content:
        details['reddit_is_archived'] = 'Yes'
    # Check locked status (treat as archived)
    if re.search(r'locked', html_content, re.IGNORECASE):
        details['reddit_is_archived'] = 'Yes'
    
    return details

def is_reddit_url(url):
    """
    Check if URL contains reddit.com
    """
    if pd.isna(url) or not isinstance(url, str):
        return False
    return 'reddit.com' in url.lower()

def identify_reddit_columns(df):
    """
    Identify columns that contain Reddit URLs
    """
    reddit_columns = []
    
    for col in df.columns:
        # Check if any cell in this column contains reddit.com
        reddit_count = df[col].astype(str).str.contains('reddit.com', case=False, na=False).sum()
        if reddit_count > 0:
            reddit_columns.append({
                'column': col,
                'reddit_urls': reddit_count,
                'total_rows': len(df)
            })
    
    return reddit_columns

def process_single_reddit_url(args):
    """Helper to process a single Reddit URL for multithreading."""
    row_idx, url = args
    html_content = get_reddit_html(url)
    details = extract_reddit_details(html_content)
    # Map to new, more descriptive column names
    mapped_details = {
        'Post Title': details.get('reddit_title', ''),
        'Posted Date & Time': details.get('reddit_posted_time', ''),
        'Posted (Relative)': details.get('reddit_time_ago', ''),
        'Total Comments': details.get('reddit_comments_count', ''),
        'Total Upvotes': details.get('reddit_score', ''),
        'Archived/Locked': details.get('reddit_is_archived', '')
    }
    return row_idx, mapped_details

def process_reddit_urls(df, url_column, progress_bar=None, status_text=None):
    new_columns = [
        'Post Title',
        'Posted Date & Time',
        'Posted (Relative)',
        'Total Comments',
        'Total Upvotes',
        'Archived/Locked'
    ]
    for col in new_columns:
        df[col] = 'Not processed'
    reddit_urls = df[df[url_column].astype(str).str.contains('reddit.com', case=False, na=False)]
    total_reddit_urls = len(reddit_urls)
    if total_reddit_urls == 0:
        return df
    for idx, (row_idx, row) in enumerate(reddit_urls.iterrows()):
        url = row[url_column]
        if status_text:
            status_text.text(f"Processing URL {idx + 1}/{total_reddit_urls}: {url[:50]}...")
        if progress_bar:
            progress_bar.progress((idx + 1) / total_reddit_urls)
        html_content = get_reddit_html(url)
        details = extract_reddit_details(html_content)
        mapped_details = {
            'Post Title': details.get('reddit_title', ''),
            'Posted Date & Time': details.get('reddit_posted_time', ''),
            'Posted (Relative)': details.get('reddit_time_ago', ''),
            'Total Comments': details.get('reddit_comments_count', ''),
            'Total Upvotes': details.get('reddit_score', ''),
            'Archived/Locked': details.get('reddit_is_archived', '')
        }
        for detail_key, detail_value in mapped_details.items():
            df.at[row_idx, detail_key] = detail_value
        time.sleep(1)
    return df

def main():
    st.title("🔍 Reddit URL Scraper")
    st.markdown("Upload a CSV/Excel file containing Reddit URLs and extract post details automatically!")
    
    # Sidebar for instructions
    st.sidebar.header("📋 Instructions")
    st.sidebar.markdown("""
    1. **Upload** your CSV or Excel file
    2. **Select** the column containing Reddit URLs
    3. **Process** the URLs to extract details
    4. **Download** the enhanced data
    
    **Extracted Details:**
    - Post Title
    - Posted Time
    - Time Ago (Reddit format)
    - Comments Count
    - Score/Votes
    - Archived Status
    """)
    
    # File upload
    st.header("📁 Upload File")
    uploaded_file = st.file_uploader(
        "Choose a CSV or Excel file",
        type=['csv', 'xlsx', 'xls'],
        help="Upload a file containing Reddit URLs in any column"
    )
    
    if uploaded_file is not None:
        try:
            # Read the file
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"✅ File uploaded successfully! Shape: {df.shape}")
            
            # Show file preview
            st.header("👀 File Preview")
            st.dataframe(df.head(), use_container_width=True)
            
            # Check for Reddit URL columns
            reddit_columns = identify_reddit_columns(df)
            
            if not reddit_columns:
                st.warning("⚠️ No Reddit URLs found in the uploaded file!")
                st.info("You can manually enter a Reddit URL below to extract its details.")
                manual_url = st.text_input("Enter a Reddit URL to process:", "https://www.reddit.com/r/Python/comments/xxxxxx/example_post/")
                if st.button("Process Reddit URL"):
                    html_content = get_reddit_html(manual_url)
                    details = extract_reddit_details(html_content)
                    st.subheader("Extracted Reddit Post Details")
                    st.json(details)
                return
            
            # If Reddit columns found, proceed as before
            if st.button("🚀 Process Reddit URLs", type="primary"):
                st.header("⏳ Processing Reddit URLs")
                
                # Create progress indicators
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                start_time = time.time()
                
                # Process the URLs
                try:
                    processed_df = process_reddit_urls(
                        df.copy(), 
                        reddit_columns[0]['column'], 
                        progress_bar, 
                        status_text
                    )
                    
                    end_time = time.time()
                    processing_time = end_time - start_time
                    
                    progress_bar.progress(1.0)
                    status_text.text("✅ Processing completed!")
                    
                    st.success(f"🎉 Processing completed in {processing_time:.1f} seconds!")
                    
                    # Show results
                    st.header("📊 Complete Results")
                    st.dataframe(processed_df, use_container_width=True)
                    
                    # Download section
                    st.header("💾 Download Results")
                    
                    # Convert to CSV for download
                    csv_buffer = io.StringIO()
                    processed_df.to_csv(csv_buffer, index=False)
                    csv_data = csv_buffer.getvalue()
                    
                    # Create filename
                    original_name = uploaded_file.name.rsplit('.', 1)[0]
                    download_filename = f"{original_name}_reddit_data.csv"
                    
                    st.download_button(
                        label="📥 Download Enhanced CSV",
                        data=csv_data,
                        file_name=download_filename,
                        mime="text/csv",
                        help="Download the original data with new Reddit details columns"
                    )
                except Exception as e:
                    st.error(f"❌ Error during processing: {str(e)}")
                    st.info("Please check your internet connection and try again.")
        except Exception as e:
            st.error(f"❌ Error reading file: {str(e)}")
            st.info("Please make sure your file is a valid CSV or Excel file.")

if __name__ == "__main__":
    main()
