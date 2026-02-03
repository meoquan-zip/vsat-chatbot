# VSAT Chatbot - RAG-Based Technical Support Assistant

A Retrieval-Augmented Generation (RAG) chatbot application designed for technical support and incident management. The system enables users to upload technical documents and receive context-aware assistance, with support for image references from uploaded documentation.

## Features

### AI Assistant
- **Document Upload & Processing**: Support for TXT, PDF, and DOCX files
- **Image Reference Support**: Embedded images in DOCX files are extracted, indexed, and referenced in chatbot responses
- **User-Specific Knowledge Base**: Each user maintains their own document collection and vector database
- **Persistent Chat History**: Conversations are saved and loaded across sessions
- **Context-Aware Responses**: Powered by Google Generative AI with retrieval from user documents

### Incident Management
- **Incident Reporting**: Create and track technical incidents with descriptions, logs, and SLA timings
- **Automated Notifications**: Email alerts for overdue incidents based on SLA thresholds
- **Incident Resolution Tracking**: Mark incidents as resolved with solution details
- **Knowledge Base Integration**: Resolved incidents are automatically added to the user's knowledge base for future reference

### Technical Capabilities
- **Vector Database**: ChromaDB for efficient document embedding and retrieval
- **Text Chunking**: Intelligent document splitting with configurable chunk size and overlap
- **OCR Fallback**: PaddleOCR for Vietnamese/multilingual text extraction from images and scanned PDFs
- **Image Placeholder System**: Images in documents are represented by `[IMAGE:filename.png]` placeholders in the text, allowing the chatbot to reference them contextually

## Requirements

- **Python**: 3.9 or higher
- **Google API Key**: Required for Google Generative AI (embeddings and chat model)
- **SMTP Server** (optional): For incident notification emails

## Installation

### 1. Clone the repository

```shell
git clone <repository-url>
cd vsat-chatbot
```

### 2. Create virtual environment (recommended)

```shell
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On Unix/macOS
source .venv/bin/activate
```

### 3. Install dependencies

```shell
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root (use `.env.template` as reference):

```env
# Google AI Configuration
GOOGLE_API_KEY=your_google_api_key_here
GENERATIVE_AI_MODEL=gemini-1.5-flash
TEXT_EMBEDDING_MODEL=models/text-embedding-004

# Database Configuration (optional)
DATABASE_URL=sqlite:///data/incidents.db

# Email Configuration (optional, for incident notifications)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FROM_EMAIL=noreply@example.com
```

### 5. Initialize database

The database will be created automatically on first run. To manually create tables:

```shell
python -c "from app.utils.db_orm import create_all_tables; create_all_tables()"
```

## Usage

### Starting the Application

```shell
streamlit run app/home.py
```

The application will open in your default browser at `http://localhost:8501`

### Using the AI Assistant

1. Navigate to the **AI Assistant** page
2. **Upload Documents**:
   - Click the file uploader in the sidebar
   - Select one or more files (TXT, PDF, DOCX, Excel)
   - Click "Process" to add them to your knowledge base
3. **Ask Questions**:
   - Type your question in the chat input
   - The chatbot will retrieve relevant context from your documents
   - If the answer references images from DOCX files, they will be displayed inline

### Managing Incidents

1. Navigate to the **Incident Report** page
2. **Create Incident**:
   - Click "Report New Incident"
   - Fill in incident details (name, description, email, SLA time, logs)
   - Submit to create and start tracking
3. **Track Incidents**:
   - View all incidents in the main panel
   - Expand an incident to see full details
   - Click "View Details" to open in sidebar for more actions
4. **Resolve Incidents**:
   - Click "Resolve" and provide a solution
   - Resolved incidents are added to your knowledge base automatically

### Image Reference Feature

When you upload DOCX files containing embedded images:
- Images are extracted to `data/kb/<username>/docs/images/<filename>/`
- Text placeholders like `[IMAGE:image_1.png]` mark their locations
- The chatbot includes these placeholders in responses when relevant
- Images are displayed below the text response with source attribution

## Project Structure

```
vsat-chatbot/
├── app/
│   ├── home.py                 # Main entry point
│   ├── pages/
│   │   ├── ai_assistant.py     # Chat interface
│   │   └── incident_report.py  # Incident management
│   └── utils/
│       ├── chatbot.py           # Chat logic and streaming
│       ├── chat_app.py          # Main app controller
│       ├── db_crud.py           # Database operations
│       ├── db_orm.py            # SQLAlchemy models
│       ├── prepare_vectordb.py  # Document processing
│       ├── save_docs.py         # Document management
│       └── email.py             # Email notifications
├── data/
│   ├── incidents.db             # SQLite database
│   └── kb/<username>/           # User-specific data
│       ├── docs/                # Uploaded documents
│       ├── chunks/              # Text chunks
│       └── vector_db/           # ChromaDB storage
├── .env                         # Environment variables
└── requirements.txt             # Python dependencies
```

## Configuration

### Document Processing Settings

Edit `app/utils/prepare_vectordb.py` to adjust:
- `CHUNK_SIZE`: Default 8000 characters
- `CHUNK_OVERLAP`: Default 800 characters

### LLM Settings

Modify system prompts in `app/utils/chatbot.py`:
- `system_instruction`: Main chatbot behavior
- Temperature and streaming settings in `ChatGoogleGenerativeAI`

## Troubleshooting

### Database Schema Updates

If you've added new columns (like `images_json`), recreate the database:

```shell
# Backup existing data first
# Then delete and recreate
rm data/incidents.db
python -c "from app.utils.db_orm import create_all_tables; create_all_tables()"
```

### Image Display Issues

- Ensure DOCX files have properly embedded images (not linked)
- Check `data/kb/<username>/docs/images/` for extracted images
- Verify file paths are absolute in the database

<!-- ### OCR Not Working

PaddleOCR requires additional dependencies. If OCR fails:

```shell
pip install paddlepaddle paddleocr
``` -->

<!-- ## License

[Add your license here]

## Contributing

[Add contribution guidelines here] -->
