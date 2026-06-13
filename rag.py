"""
rag.py — Sistem RAG (Retrieval-Augmented Generation)

Alur kerja:
1. Admin upload PDF → extract teks → potong jadi chunks
2. Setiap chunk di-embed → disimpan ke FAISS index
3. User tanya → embed pertanyaan → cari chunk paling mirip
4. Chunk relevan + pertanyaan → dikirim ke LLM → jawaban
"""

import os
import pickle
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Konfigurasi ────────────────────────────────────────────────────────────────
FAISS_INDEX_PATH  = "rag_data/faiss_index.bin"   # file index FAISS
CHUNKS_PATH       = "rag_data/chunks.pkl"         # file teks chunks
PDF_DIR           = "rag_data/pdfs"               # folder PDF admin
EMBED_MODEL_NAME  = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LLM_MODEL_NAME    = "llama-3.1-8b-instant"
CHUNK_SIZE        = 500    # jumlah karakter per chunk
CHUNK_OVERLAP     = 50     # overlap antar chunk agar konteks tidak putus
TOP_K             = 4      # ambil 4 chunk paling relevan

# ── Disease knowledge base (hardcoded) ────────────────────────────────────────
# Ini akan digabung dengan isi PDF saat build index
DISEASE_KNOWLEDGE = """
Flea Allergy (Alergi Kutu):
Flea allergy dermatitis adalah reaksi alergi terhadap gigitan kutu pada kucing.
Gejala: gatal hebat, kerontokan bulu, kulit kemerahan, lesi di punggung dan ekor.
Penanganan: obat antikutu (flukonazol, ivermectin), shampo antikutu, jaga kebersihan lingkungan.
Pencegahan: perawatan rutin, sterilkan tempat tidur hewan, pisahkan dari hewan lain yang terinfeksi.

Ringworm (Kurap / Dermatophytosis):
Infeksi jamur menular yang disebabkan Microsporum canis, Trichophyton mentagrophytes.
Gejala: bercak bulat bersisik, kebotakan melingkar, kulit merah dan gatal.
Sangat menular ke manusia dan hewan lain — tangani dengan sarung tangan!
Penanganan: antijamur topikal (miconazole, clotrimazole), antijamur oral (itraconazole), isolasi hewan.
Pencegahan: cuci tangan setelah memegang kucing, desinfeksi peralatan dan lingkungan.

Scabies (Kudis / Sarcoptic Mange):
Infeksi tungau Sarcoptes scabiei atau Notoedres cati yang menggali ke dalam kulit.
Gejala: gatal ekstrem, kerak tebal di telinga dan wajah, penebalan kulit, kerontokan bulu.
Penanganan: antiparasit (ivermectin, selamectin), mandi sulfur, isolasi dari hewan lain.
Pencegahan: hindari kontak dengan hewan liar, pemeriksaan rutin ke dokter hewan.

Kulit Sehat (Healthy):
Ciri kulit kucing sehat: bulu berkilau, tidak ada kerontokan berlebih, kulit bersih tanpa lesi.
Perawatan rutin: mandi 1-2x seminggu, sisir bulu, berikan nutrisi seimbang.
Jadwalkan vaksinasi dan pemeriksaan dokter hewan setiap 6 bulan sekali.
"""

# ── Lazy load models (tidak load saat import, hanya saat dipakai) ──────────────
_embed_model = None
_llm_pipeline = None
_faiss_index = None
_chunks = None


def get_embed_model():
    """Load embedding model (sekali saja, disimpan di memory)."""
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        print(f"[RAG] Loading embedding model: {EMBED_MODEL_NAME}")
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
        print("[RAG] Embedding model loaded!")
    return _embed_model


def get_llm():
    """Load Groq LLM client."""
    global _llm_pipeline
    if _llm_pipeline is None:
        from langchain_groq import ChatGroq
        print("[RAG] Connecting to Groq API...")
        _llm_pipeline = ChatGroq(
            model=LLM_MODEL_NAME,
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.7,
            max_tokens=512,
        )
        print("[RAG] Groq LLM ready!")
    return _llm_pipeline


# ── Text Chunking ──────────────────────────────────────────────────────────────
def split_text(text: str, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> list[str]:
    """
    Potong teks panjang menjadi potongan kecil (chunks).
    overlap: beberapa karakter dari chunk sebelumnya ikut di chunk berikutnya
    agar konteks tidak terputus di tengah kalimat.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c.strip() for c in chunks if len(c.strip()) > 50]


# ── PDF Extraction ─────────────────────────────────────────────────────────────
def extract_pdf_text(pdf_path: str) -> str:
    """Extract semua teks dari file PDF menggunakan PyMuPDF."""
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


# ── Build / Update FAISS Index ─────────────────────────────────────────────────
def build_index():
    """
    Buat FAISS index dari:
    1. Semua PDF di folder rag_data/pdfs/
    2. Disease knowledge base (hardcoded)
    
    Simpan index dan chunks ke disk supaya tidak perlu rebuild setiap restart.
    """
    import faiss

    Path("rag_data/pdfs").mkdir(parents=True, exist_ok=True)

    all_text = DISEASE_KNOWLEDGE  # mulai dari knowledge base

    # Tambahkan teks dari semua PDF
    pdf_files = list(Path(PDF_DIR).glob("*.pdf"))
    print(f"[RAG] Found {len(pdf_files)} PDF file(s)")
    for pdf_path in pdf_files:
        print(f"[RAG] Extracting: {pdf_path.name}")
        all_text += "\n\n" + extract_pdf_text(str(pdf_path))

    # Potong jadi chunks
    chunks = split_text(all_text)
    print(f"[RAG] Total chunks: {len(chunks)}")

    # Embed semua chunks
    embed_model = get_embed_model()
    embeddings = embed_model.encode(chunks, show_progress_bar=True)
    embeddings = np.array(embeddings, dtype=np.float32)

    # Normalisasi untuk cosine similarity
    faiss.normalize_L2(embeddings)

    # Buat FAISS index (IndexFlatIP = Inner Product = cosine similarity setelah normalisasi)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    # Simpan ke disk
    faiss.write_index(index, FAISS_INDEX_PATH)
    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(chunks, f)

    print(f"[RAG] Index saved! {index.ntotal} vectors")
    return index, chunks


def load_index():
    """Load FAISS index dari disk (kalau sudah ada)."""
    import faiss
    global _faiss_index, _chunks

    if _faiss_index is not None:
        return _faiss_index, _chunks

    if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(CHUNKS_PATH):
        print("[RAG] Loading existing FAISS index...")
        _faiss_index = faiss.read_index(FAISS_INDEX_PATH)
        with open(CHUNKS_PATH, "rb") as f:
            _chunks = pickle.load(f)
        print(f"[RAG] Index loaded! {_faiss_index.ntotal} vectors")
        return _faiss_index, _chunks
    else:
        # Belum ada index → build dari awal
        print("[RAG] No index found, building...")
        _faiss_index, _chunks = build_index()
        return _faiss_index, _chunks


# ── Retrieval ──────────────────────────────────────────────────────────────────
def retrieve(query: str, top_k=TOP_K) -> list[str]:
    """
    Cari chunks paling relevan untuk query user.
    
    Cara kerja:
    1. Embed query → vektor angka
    2. Cari vektor paling mirip di FAISS index (nearest neighbor)
    3. Return teks chunks yang sesuai
    """
    import faiss
    index, chunks = load_index()
    embed_model = get_embed_model()

    # Embed query
    query_vec = embed_model.encode([query])
    query_vec = np.array(query_vec, dtype=np.float32)
    faiss.normalize_L2(query_vec)

    # Search
    scores, indices = index.search(query_vec, top_k)

    # Filter hasil dengan score rendah (tidak relevan)
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if score > 0.3 and idx < len(chunks):  # threshold relevansi
            results.append(chunks[idx])

    return results


# ── Generation ─────────────────────────────────────────────────────────────────
def generate_answer(query: str, context_chunks: list[str]) -> str:
    """Generate jawaban via Groq API."""
    from langchain_core.messages import SystemMessage, HumanMessage
    
    llm = get_llm()
    context = "\n\n".join(context_chunks)

    messages = [
        SystemMessage(content="""Kamu adalah asisten veteriner virtual untuk aplikasi Sakti Pet Care CatSkin AI.
Tugasmu adalah menjawab pertanyaan tentang kesehatan kulit kucing berdasarkan konteks yang diberikan.
Jawab dalam bahasa Indonesia yang ramah dan mudah dipahami pemilik kucing awam.
Jika informasi tidak ada di konteks, katakan dengan jujur dan sarankan konsultasi ke dokter hewan."""),
        HumanMessage(content=f"""Konteks:
{context}

Pertanyaan: {query}""")
    ]

    response = llm.invoke(messages)
    return response.content


# ── Main RAG function ──────────────────────────────────────────────────────────
def ask(query: str) -> dict:
    """
    Fungsi utama yang dipanggil dari FastAPI.
    Return: jawaban + sumber chunks yang dipakai
    """
    # 1. Retrieve chunks relevan
    relevant_chunks = retrieve(query)

    if not relevant_chunks:
        return {
            "answer": "Maaf, saya tidak menemukan informasi yang relevan. Silakan konsultasikan ke dokter hewan terdekat.",
            "sources": []
        }

    # 2. Generate jawaban
    answer = generate_answer(query, relevant_chunks)

    return {
        "answer": answer,
        "sources": relevant_chunks[:2]  # tampilkan 2 sumber teratas
    }