import json
import os
import requests
import numpy as np
import re
from langdetect import detect, DetectorFactory
from transformers import pipeline
from sklearn.metrics.pairwise import euclidean_distances
from keybert import KeyBERT

# Ensure reproducibility
DetectorFactory.seed = 0
np.random.seed(42)

# Comprehensive Keyword Set
RELEVANT_KEYWORDS = {
    # Personal Development
    'self-improvement', 'growth', 'potential', 'mindset', 'discipline', 
    'motivation', 'resilience', 'personal transformation', 'self-mastery',
    
    # Psychological Insights
    'psychology', 'emotional intelligence', 'subconscious', 'cognitive skills', 
    'mental frameworks', 'perception', 'self-awareness', 'human nature',
    
    # Skill Acquisition
    'skill', 'mastery', 'expertise', 'learning', 'practice', 'continuous improvement', 
    'deliberate practice', 'performance', 'talent development',
    
    # Communication & Interpersonal Skills
    'communication', 'persuasion', 'charisma', 'social skills', 'influence', 
    'negotiation', 'relationship building', 'emotional connection',
    
    # Professional & Personal Strategy
    'strategy', 'goal setting', 'productivity', 'success principles', 'decision making', 
    'personal philosophy', 'life design', 'overcoming obstacles',
    
    # Emotional Management
    'emotions', 'emotional control', 'self-regulation', 'mental toughness', 
    'confidence', 'inner strength', 'overcoming fear', 'ego management',
    
    # Specific Themes
    'seduction', 'art of living', 'minimalism', 'stoicism', 'negotiation', 
    'personal power', 'creativity', 'entrepreneurship', 'life lessons'
}

# Scoring Weights
KEYWORD_WEIGHT = 0.4
EMOTION_WEIGHT = 0.3
DESCRIPTION_WEIGHT = 0.3

def safe_load_json(file_path):
    """Safely load JSON file with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return []
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in file: {file_path}")
        return []

def fetch_book_details(work_key):
    """Fetch book details from Open Library with robust error handling."""
    try:
        url = f"https://openlibrary.org{work_key}.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        description = data.get('description', '')

        if isinstance(description, dict):
            description = description.get('value', '')
        
        return str(description)[:1500] or "No description available."
    
    except (requests.RequestException, ValueError) as e:
        print(f"❌ Book details fetch error: {e}")
        return "No description available."

def fetch_books_from_open_library(subject="self_help", limit=100):
    """Fetch books from Open Library with comprehensive error handling and description filtering."""
    try:
        url = f"https://openlibrary.org/subjects/{subject}.json?limit={limit}"
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        data = response.json()
        books = []
        for entry in data.get('works', []):
            work_key = entry['key']
            description = fetch_book_details(work_key)

            # Skip books with empty or too-short descriptions
            if not description or len(description.split()) < 50:
                continue

            books.append({
                "title": entry['title'],
                "authors": [author.get('name', 'Unknown') for author in entry.get('authors', [])],
                "description": description
            })

        return books
    except (requests.RequestException, ValueError) as e:
        print(f"❌ Open Library fetch error: {e}")
        return []


def is_relevant_book(book, seed_keywords):
    """Loosened relevance check - allow if ANY match is found, rather than requiring both."""
    description = book.get('description', '').lower()
    title = book.get('title', '').lower()

    # Skip books with descriptions that are too short
    if len(description) < 50:
        return False

    # Allow books if they match EITHER relevant keywords OR seed keywords
    relevant_match = any(keyword in description or keyword in title for keyword in RELEVANT_KEYWORDS)
    seed_match = any(keyword in description or keyword in title for keyword in seed_keywords)

    return relevant_match or seed_match



def extract_keywords(text, additional_keywords=None):
    """Enhanced keyword extraction."""
    try:
        text = str(text)[:1500]
        
        # Extract keyphrases
        keywords = kw_model.extract_keywords(
            text, 
            keyphrase_ngram_range=(1, 3), 
            stop_words='english', 
            top_n=15
        )
        
        # Process and filter keywords
        extracted_keywords = {
            kw[0].lower() for kw in keywords 
            if len(kw[0].split()) <= 3
        }
        
        if additional_keywords:
            extracted_keywords.update(additional_keywords)
        
        return extracted_keywords
    except Exception as e:
        print(f"❌ Keyword extraction error: {e}")
        return set()

def analyze_emotions(text, emotion_pipeline):
    """Robust emotion analysis."""
    try:
        text = str(text)[:1000]
        
        result = emotion_pipeline(text, top_k=3)
        
        # Handle different pipeline output formats
        if result and isinstance(result[0], list):
            result = result[0]
        
        top_emotions = sorted(result, key=lambda x: -x['score'])[:3]
        return {emo['label']: emo['score'] for emo in top_emotions}

    except Exception as e:
        print(f"❌ Emotion analysis failed: {e}")
        return {}

def vectorize_emotions(emotions, all_emotions):
    """Convert emotions to numerical vector."""
    return np.array([emotions.get(emotion, 0.0) for emotion in all_emotions])

def calculate_description_relevance(description, seed_keywords):
    """Calculate description relevance score."""
    description = description.lower()
    
    relevance_score = sum(
        description.count(keyword) * 1.5 
        for keyword in seed_keywords 
        if keyword in description
    )
    
    return min(relevance_score / len(seed_keywords), 1.0)

def recommend_books(seed_emotions, seed_keywords, candidate_books, emotion_pipeline, all_emotions, top_n=7):
    """Advanced book recommendation algorithm."""
    seed_vector = vectorize_emotions(seed_emotions, all_emotions)
    recommendations = []

    for book in candidate_books:
        # Filter books
        if not is_relevant_book(book, seed_keywords):
            continue

        # Emotion and keyword analysis
        emotions = analyze_emotions(book['description'] or book['title'], emotion_pipeline)
        emotion_vector = vectorize_emotions(emotions, all_emotions)

        book_keywords = extract_keywords(book['description'], seed_keywords)
        keyword_overlap = len(seed_keywords.intersection(book_keywords))

        # Compute similarity scores
        emotion_distance = np.linalg.norm(seed_vector - emotion_vector)
        emotion_similarity = 1 / (1 + emotion_distance)

        keyword_score = keyword_overlap / max(len(seed_keywords), 1)
        description_relevance = calculate_description_relevance(book['description'], seed_keywords)

        # Weighted scoring
        total_score = (
            KEYWORD_WEIGHT * keyword_score + 
            EMOTION_WEIGHT * emotion_similarity + 
            DESCRIPTION_WEIGHT * description_relevance
        )

        recommendations.append({
            'title': book['title'],
            'authors': book['authors'],
            'description': book['description'],
            'score': total_score,
            'keyword_score': keyword_score,
            'emotion_score': emotion_similarity,
            'description_relevance': description_relevance
        })

    # Sort and filter recommendations
    recommendations = sorted(recommendations, key=lambda x: x['score'], reverse=True)[:top_n]

    # Print detailed recommendations
    print("\n📚 Precision Book Recommendations:\n")
    for idx, rec in enumerate(recommendations, 1):
        print(f"{idx}. 🔹 {rec['title']}")
        print(f"   By: {', '.join(rec['authors'])}")
        print(f"   Overall Relevance: {rec['score']:.3f}")
        print(f"   Keyword Match: {rec['keyword_score']:.2f}")
        print(f"   Emotional Alignment: {rec['emotion_score']:.2f}")
        print(f"   📖 Description: {rec['description'][:300]}{'...' if len(rec['description']) > 300 else ''}")
        print("-" * 60)

    return recommendations

def main():
    # Paths and setup
    BASE_PATH = r'C:\Users\ajeet\book-recommender'
    REVIEWS_PATH = os.path.join(BASE_PATH, 'data', 'enriched_reviews.json')

    # Initialize models
    emotion_pipeline = pipeline("text-classification", model="bhadresh-savani/distilbert-base-uncased-emotion")
    global kw_model
    kw_model = KeyBERT()

    # Load personal books
    personal_books = safe_load_json(REVIEWS_PATH)
    
    if not personal_books:
        print("❌ No books found in your collection.")
        return

    # Display books
    print("\n📚 Your Books:\n")
    for idx, book in enumerate(personal_books, 1):
        print(f"{idx}. {book['book_title']}")

    # Book selection
    while True:
        seed_title = input("\nEnter the title of a book you've read (exactly as shown above): ").strip()
        seed_book = next((book for book in personal_books if book['book_title'] == seed_title), None)

        if seed_book:
            break
        print(f"❌ Book '{seed_title}' not found. Try again.")

    # Extract seed book characteristics
    seed_emotions = dict(seed_book.get('top_emotions', {}))
    seed_keywords = extract_keywords(seed_book['review_text'])

    # Subject selection
    subjects = ['self_help', 'psychology', 'philosophy', 'personal_development']
    for subject in subjects:
        print(f"\n🔍 Searching for books in '{subject}' category...")
        candidate_books = fetch_books_from_open_library(subject, limit=150)
        
        if candidate_books:
            break
    
    if not candidate_books:
        print("❌ No books found across multiple subjects.")
        return

    # Define emotions for vectorization
    all_emotions = ["joy", "curiosity", "love", "anger", "fear", "sadness"]
    
    # Generate recommendations
    recommend_books(seed_emotions, seed_keywords, candidate_books, emotion_pipeline, all_emotions)

if __name__ == "__main__":
    print("🚀 Intelligent Book Recommendation System\n")
    main()
