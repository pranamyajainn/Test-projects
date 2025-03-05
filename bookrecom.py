import json
import requests
import numpy as np
import re
from langdetect import detect, DetectorFactory
from transformers import pipeline
from sklearn.metrics.pairwise import euclidean_distances
from keybert import KeyBERT

# Ensure language detection is consistent
DetectorFactory.seed = 0

# Predefined relevant keywords for self-help books
RELEVANT_KEYWORDS = {'learning', 'skills', 'productivity', 'focus', 'mastery', 'habits', 'growth', 'improvement', 'psychology', 'success'}

# Step 1 — Load your existing books
def load_existing_books():
    with open(r'C:\Users\ajeet\book-recommender\data\enriched_reviews.json', 'r', encoding='utf-8') as file:
        return json.load(file)

# Step 2 — Get already read book titles to exclude from recommendations
def get_existing_titles(books):
    return {book['book_title'].lower() for book in books}

# Fetch detailed book descriptions from Open Library
def fetch_book_details(work_key):
    url = f"https://openlibrary.org{work_key}.json"
    response = requests.get(url)

    if response.status_code != 200:
        return None

    data = response.json()
    description = data.get('description', '')

    # Handle both dict and string descriptions
    if isinstance(description, dict):
        description = description.get('value', '')

    return description

# Step 3 — Fetch books from Open Library by subject
def fetch_books_from_open_library(subject="self_help", limit=30):
    url = f"https://openlibrary.org/subjects/{subject}.json?limit={limit}"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"❌ Failed to fetch books from Open Library for subject: {subject}")
        return []

    data = response.json()
    books = []
    for entry in data.get('works', []):
        work_key = entry['key']
        description = fetch_book_details(work_key) or "No description available."

        books.append({
            "title": entry['title'],
            "authors": [author['name'] for author in entry.get('authors', [])],
            "description": description
        })

    return books

# Step 4 — Advanced Filtering: Remove junk books
def is_relevant_book(book):
    description = book.get('description', '').lower()

    # 1. Check minimum description length
    if len(description) < 100:
        return False

    # 2. Language check (skip non-English books)
    try:
        if detect(description) != 'en':
            return False
    except Exception:
        return False  # If langdetect fails, skip book

    # 3. Check if at least one relevant keyword exists in description
    if not any(keyword in description for keyword in RELEVANT_KEYWORDS):
        return False

    # 4. Remove known irrelevant genres
    if re.search(r'\bfashion\b|\bstyle\b|\bdiet\b|\bweight\b|\bromance\b', description):
        return False

    return True

# Step 5 — Extract keywords for topic similarity
kw_model = KeyBERT()

def extract_keywords(text):
    keywords = kw_model.extract_keywords(text, keyphrase_ngram_range=(1, 2), stop_words='english', top_n=5)
    return {kw[0] for kw in keywords}

# Step 6 — Analyze emotions
def analyze_emotions(text, emotion_pipeline):
    try:
        result = emotion_pipeline(text, top_k=None)  
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
            all_emotions = result[0]  
        else:
            all_emotions = result  

        top_emotions = sorted(all_emotions, key=lambda x: -x['score'])[:3]
        return {emo['label']: emo['score'] for emo in top_emotions}

    except Exception as e:
        print(f"❌ Emotion analysis failed for text: {text[:50]}... - Error: {e}")
        return {}

# Step 7 — Convert emotions to numerical vector
def vectorize_emotions(emotions, all_emotions):
    return np.array([emotions.get(emotion, 0.0) for emotion in all_emotions])

# Step 8 — Recommend books based on emotions + topics
def recommend_new_books(seed_emotions, seed_keywords, candidate_books, emotion_pipeline, all_emotions, top_n=5):
    seed_vector = vectorize_emotions(seed_emotions, all_emotions)

    vectors = []
    titles = []
    descriptions = []
    topic_scores = []

    for book in candidate_books:
        emotions = analyze_emotions(book['description'] or book['title'], emotion_pipeline)
        vector = vectorize_emotions(emotions, all_emotions)
        book_keywords = extract_keywords(book['description'])

        common_keywords = seed_keywords.intersection(book_keywords)

        # 🚨 Skip books with no keyword overlap (ensures thematic relevance)
        if len(common_keywords) == 0:
            continue

        vectors.append(vector)
        titles.append(book['title'])
        descriptions.append(book['description'] or "No description available.")

        topic_score = len(common_keywords) / max(len(seed_keywords), 1)
        topic_scores.append(topic_score)

        print(f"\n🔍 DEBUG: Extracted Keywords for '{book['title']}': {book_keywords}")
        print(f"🔍 DEBUG: Common Keywords Found: {common_keywords}")

    if not vectors:
        print("\n❌ No suitable book recommendations found after filtering.")
        return

    distances = euclidean_distances([seed_vector], vectors)[0]
    similarity_scores = 1 - (distances / np.max(distances))

    recommendations = sorted(zip(titles, similarity_scores, topic_scores, descriptions), key=lambda x: (-x[1], -x[2]))[:top_n]

    print("\n📚 Recommended Books Based on Emotions & Topics:\n")
    for title, score, topic_score, description in recommendations:
        print(f"\n🔹 {title}")
        print(f"   Similarity: {score:.3f}")
        print(f"   Topic Match Score: {topic_score:.2f}")
        print(f"   📖 What It’s About: {description.strip()[:300]}{'...' if len(description) > 300 else ''}")
        print("-" * 60)

# Main Execution
def main():
    emotion_pipeline = pipeline("text-classification", model="bhadresh-savani/distilbert-base-uncased-emotion")

    # Load personal reviews
    personal_books = load_existing_books()
    existing_titles = get_existing_titles(personal_books)

    print("\n📚 Your Books:\n")
    for idx, book in enumerate(personal_books, 1):
        print(f"{idx}. {book['book_title']}")

    # Ask for seed book
    seed_title = input("\nEnter the title of a book you've read (exactly as shown above): ").strip().lower()
    seed_book = next((book for book in personal_books if book['book_title'].lower() == seed_title), None)

    if not seed_book:
        print(f"❌ Book '{seed_title}' not found in your personal collection.")
        return

    seed_emotions = {emotion: score for emotion, score in seed_book['top_emotions']}
    seed_keywords = extract_keywords(seed_book['review_text'])

    # Get new books
    subject = input("Enter a subject (like self_help, psychology, or philosophy): ").strip().lower()
    candidate_books = fetch_books_from_open_library(subject=subject, limit=50)

    # Apply filtering
    candidate_books = [book for book in candidate_books if is_relevant_book(book) and book['title'].lower() not in existing_titles]

    if not candidate_books:
        print("❌ No suitable books found after filtering.")
        return

    # Recommend books
    all_emotions = ["joy", "curiosity", "love", "anger", "fear", "sadness"]
    recommend_new_books(seed_emotions, seed_keywords, candidate_books, emotion_pipeline, all_emotions)

if __name__ == "__main__":
    print("🚀 Starting New Book Recommendation System...\n")
    main()
