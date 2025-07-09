# Automated Due Diligence Research Platform

A secure, AI-powered platform for conducting comprehensive due diligence analysis on public companies for acquisition purposes.

## 📋 Features

### Core Functionality
- **Company Search**: Search for public companies by name or ticker symbol
- **Financial Data Integration**: Real-time financial data from multiple free APIs
- **AI-Powered Analysis**: Comprehensive due diligence reports (when configured)
- **Risk Assessment**: Automated risk evaluation and scoring
- **Secure Architecture**: Enterprise-grade security measures

### Data Sources
- **Financial Modeling Prep (FMP)**: Company profiles, financial statements
- **Alpha Vantage**: Market news and sentiment analysis
- **Finnhub**: Additional market data and metrics

### Security Features
- Input validation and sanitization
- Rate limiting and abuse prevention
- Security headers and CORS protection
- Suspicious activity detection
- Comprehensive logging

## 🛠 Technology Stack

### Backend
- **Flask**: Python web framework
- **Flask-CORS**: Cross-origin resource sharing
- **Flask-SQLAlchemy**: Database ORM
- **Requests**: HTTP client for API calls
- **Python-dotenv**: Environment variable management

### Frontend
- **React**: Modern JavaScript framework
- **Tailwind CSS**: Utility-first CSS framework
- **Shadcn/UI**: High-quality UI components
- **Lucide Icons**: Beautiful icon library
- **Vite**: Fast build tool

### APIs & Services
- **Financial Modeling Prep**: Financial data
- **Alpha Vantage**: Market news
- **Gemini AI**: Analysis engine (optional)

## 🔧 Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 20+
- API keys for external services

### Environment Variables
Create a `.env` file in the project root:

```env
# Required API Keys
FMP_API_KEY=your_financial_modeling_prep_api_key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key
FINNHUB_API_KEY=your_finnhub_api_key

# Optional: For AI-powered analysis
GOOGLE_API_KEY=your_gemini_api_key

# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your_secret_key
```

### Local Development

1. **Clone the repository**
```bash
git clone <repository-url>
cd due-diligence-platform
```

2. **Backend Setup**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the Flask application
python src/main.py
```

3. **Frontend Setup**
```bash
cd ../due-diligence-frontend
npm install
npm run dev
```

### Production Deployment
The platform is deployed using Manus deployment services with automatic scaling and monitoring.

## 📊 API Endpoints

### Company Search
```
POST /api/search-company
Content-Type: application/json

{
  "query": "AAPL"
}
```

### Company Profile
```
GET /api/company-profile/{symbol}
```

### Financial Statements
```
GET /api/financial-statements/{symbol}
```

### Market News
```
GET /api/market-news/{symbol}
```

### AI Analysis
```
POST /api/analyze-company
Content-Type: application/json

{
  "symbol": "AAPL",
  "analysis_type": "general|financial|risk"
}
```

### Health Check
```
GET /api/health
```

