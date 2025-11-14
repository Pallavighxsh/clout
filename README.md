# Clout: A Social Media Market Research & Long-Form Draft Generator

(Not a LinkedIn Post Writer)

Clout is a Python-based social media market-research and long-form draft creation tool. It does not produce final, ready-to-publish LinkedIn posts. Instead, it generates deep, research-enriched raw material you can refine into polished content.

This tool scrapes your blog posts, performs SERP research, extracts entities, and produces three exploratory long-form narrative drafts for each blog post.

### ⚠️ Important Disclaimer

The output of this tool is not a LinkedIn post.

It is intentionally:

-Filled with data

-Unpolished

-Dense

-Draft-like

You are expected to edit, shorten, restructure, and refine this raw material before posting it publicly.

Clout helps you think, not publish.

### 🚀 Features

-Scrapes blog pages and extracts readable content

-Runs SERP market research using your SERP API key

-Scrapes top SERP results for additional context

-Extracts:

    -Emails
    
    -Proper nouns (industry keywords / market intelligence!)
    
    -Entities that matter for audience and competitor analysis (frequently occuring SEO keywords!)
  
-Generates three long-form draft variants per blog:

    -Thought Leadership
    
    -Story Narrative
    
    -Actionable / Framework
  
-Streams LLM output live in terminal

-Saves all drafts into clout_posts.xlsx

-Creates a serp_debug sheet for full auditability

### 🔍 What Are SERP Links?

When the tool performs a search (via SerpAPI), it retrieves top results related to your blog.

These links represent:

    -Competitor articles
    
    -Think pieces
    
    -Market commentary
    
    -Industry pages
    
    -Related editorial content
    
The text from these pages enriches your drafts with broader context. These exact links are stored in the serp_debug sheet so you always know the research sources.

### 🚀 Installation (Short & Plain)

-Set up a Python virtual environment on your machine (optional but recommended).

-Install the required dependencies listed in requirements.txt.

-In the script, find the variable BLOG_URLS and add some links on topics you want your long-form post to be based on. (Not necessarily blogs, could also be product pages.)

-The above step is important. This tool will research the topics from the links further but we have to give it some direction.

### 🧠 Model Setup (Phi-3 Mini)

-Download the model file Phi-3-mini-4k-instruct-q4.gguf from HuggingFace or Microsoft’s official model page.

-Place the downloaded GGUF model file inside the models folder.

-Provide the full path to the model file in your .env so the script knows where to load it from. (nano .env)

### 🔑 SERP API Setup

-Create an account on SerpAPI (free tier is enough for this tool).

-Generate your personal API key from your SerpAPI dashboard.

-Add this API key to your .env file so the script can run searches and gather market-research context.

### Don't forget to add your SERP API! The entire research process relies on this.
