from flask import Blueprint, jsonify, request
from flask_cors import cross_origin
import os
import requests
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage
import json
from src.security import security_manager, require_valid_input, validate_symbol_input

# Load environment variables
load_dotenv()

due_diligence_bp = Blueprint('due_diligence', __name__)

# Initialize Gemini LLM
try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=os.getenv('GOOGLE_API_KEY'),
        temperature=0.6
    )
except Exception as e:
    print(f"Warning: Failed to initialize Gemini LLM: {e}")
    llm = None

# API Keys
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')
FMP_API_KEY = os.getenv('FMP_API_KEY')

@due_diligence_bp.route('/search-company', methods=['POST'])
@cross_origin()
@security_manager.rate_limit(max_requests=20, window_minutes=1)
@require_valid_input('query', max_length=100, allow_special_chars=False)
def search_company():
    """Search for company information by symbol or name"""
    try:
        data = request.json
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'error': 'Query parameter is required'}), 400
        
        # Validate API key
        is_valid, message = security_manager.validate_api_key(FMP_API_KEY, 'Financial Modeling Prep')
        if not is_valid:
            return jsonify({'error': message}), 500
        
        # Search using FMP API
        search_url = f"https://financialmodelingprep.com/api/v3/search?query={query}&apikey={FMP_API_KEY}"
        
        try:
            response = requests.get(search_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            security_manager.log_security_event('API_ERROR', f'FMP search failed: {str(e)}')
            return jsonify({'error': 'External API temporarily unavailable'}), 503
        
        if response.status_code == 200:
            companies = response.json()
            # Limit and sanitize results
            safe_companies = []
            for company in companies[:10]:  # Limit to top 10 results
                safe_company = {
                    'symbol': security_manager.validate_input(company.get('symbol', ''), 10, False),
                    'name': security_manager.validate_input(company.get('name', ''), 200),
                    'currency': security_manager.validate_input(company.get('currency', ''), 10, False),
                    'stockExchange': security_manager.validate_input(company.get('stockExchange', ''), 50),
                    'exchangeShortName': security_manager.validate_input(company.get('exchangeShortName', ''), 20, False)
                }
                safe_companies.append(safe_company)
            
            return jsonify({'companies': safe_companies})
        else:
            return jsonify({'error': 'Failed to search companies'}), 500
            
    except Exception as e:
        security_manager.log_security_event('SEARCH_ERROR', f'Unexpected error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@due_diligence_bp.route('/company-profile/<symbol>', methods=['GET'])
@cross_origin()
@security_manager.rate_limit(max_requests=30, window_minutes=1)
@validate_symbol_input
def get_company_profile(symbol):
    """Get detailed company profile"""
    try:
        # Validate API key
        is_valid, message = security_manager.validate_api_key(FMP_API_KEY, 'Financial Modeling Prep')
        if not is_valid:
            return jsonify({'error': message}), 500
        
        # Get company profile from FMP
        profile_url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={FMP_API_KEY}"
        
        try:
            response = requests.get(profile_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            security_manager.log_security_event('API_ERROR', f'FMP profile failed: {str(e)}')
            return jsonify({'error': 'External API temporarily unavailable'}), 503
        
        if response.status_code == 200:
            profile_data = response.json()
            if profile_data:
                # Sanitize profile data
                profile = profile_data[0]
                safe_profile = {
                    'symbol': security_manager.validate_input(profile.get('symbol', ''), 10, False),
                    'companyName': security_manager.validate_input(profile.get('companyName', ''), 200),
                    'sector': security_manager.validate_input(profile.get('sector', ''), 100),
                    'industry': security_manager.validate_input(profile.get('industry', ''), 100),
                    'description': security_manager.validate_input(profile.get('description', ''), 2000),
                    'mktCap': profile.get('mktCap') if isinstance(profile.get('mktCap'), (int, float)) else None,
                    'price': profile.get('price') if isinstance(profile.get('price'), (int, float)) else None,
                    'fullTimeEmployees': profile.get('fullTimeEmployees') if isinstance(profile.get('fullTimeEmployees'), (int, float)) else None,
                    'website': security_manager.validate_input(profile.get('website', ''), 200),
                    'country': security_manager.validate_input(profile.get('country', ''), 50, False),
                    'currency': security_manager.validate_input(profile.get('currency', ''), 10, False)
                }
                return jsonify({'profile': safe_profile})
            else:
                return jsonify({'error': 'Company not found'}), 404
        else:
            return jsonify({'error': 'Failed to fetch company profile'}), 500
            
    except Exception as e:
        security_manager.log_security_event('PROFILE_ERROR', f'Unexpected error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@due_diligence_bp.route('/financial-statements/<symbol>', methods=['GET'])
@cross_origin()
@security_manager.rate_limit(max_requests=20, window_minutes=1)
@validate_symbol_input
def get_financial_statements(symbol):
    """Get financial statements for a company"""
    try:
        # Validate API key
        is_valid, message = security_manager.validate_api_key(FMP_API_KEY, 'Financial Modeling Prep')
        if not is_valid:
            return jsonify({'error': message}), 500
        
        statements = {}
        
        # Income Statement
        income_url = f"https://financialmodelingprep.com/api/v3/income-statement/{symbol}?limit=5&apikey={FMP_API_KEY}"
        try:
            income_response = requests.get(income_url, timeout=10)
            if income_response.status_code == 200:
                statements['income_statement'] = income_response.json()
        except requests.RequestException:
            statements['income_statement'] = []
        
        # Balance Sheet
        balance_url = f"https://financialmodelingprep.com/api/v3/balance-sheet-statement/{symbol}?limit=5&apikey={FMP_API_KEY}"
        try:
            balance_response = requests.get(balance_url, timeout=10)
            if balance_response.status_code == 200:
                statements['balance_sheet'] = balance_response.json()
        except requests.RequestException:
            statements['balance_sheet'] = []
        
        # Cash Flow Statement
        cashflow_url = f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{symbol}?limit=5&apikey={FMP_API_KEY}"
        try:
            cashflow_response = requests.get(cashflow_url, timeout=10)
            if cashflow_response.status_code == 200:
                statements['cash_flow'] = cashflow_response.json()
        except requests.RequestException:
            statements['cash_flow'] = []
        
        return jsonify({'financial_statements': statements})
        
    except Exception as e:
        security_manager.log_security_event('FINANCIAL_ERROR', f'Unexpected error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@due_diligence_bp.route('/market-news/<symbol>', methods=['GET'])
@cross_origin()
@security_manager.rate_limit(max_requests=15, window_minutes=1)
@validate_symbol_input
def get_market_news(symbol):
    """Get market news for a company"""
    try:
        # Validate API key
        is_valid, message = security_manager.validate_api_key(ALPHA_VANTAGE_API_KEY, 'Alpha Vantage')
        if not is_valid:
            return jsonify({'error': message}), 500
        
        # Get news from Alpha Vantage
        news_url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        
        try:
            response = requests.get(news_url, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            security_manager.log_security_event('API_ERROR', f'Alpha Vantage news failed: {str(e)}')
            return jsonify({'error': 'News service temporarily unavailable'}), 503
        
        if response.status_code == 200:
            news_data = response.json()
            return jsonify({'news': news_data})
        else:
            return jsonify({'error': 'Failed to fetch news'}), 500
            
    except Exception as e:
        security_manager.log_security_event('NEWS_ERROR', f'Unexpected error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@due_diligence_bp.route('/analyze-company', methods=['POST'])
@cross_origin()
@security_manager.rate_limit(max_requests=5, window_minutes=1)  # Lower limit for AI analysis
@require_valid_input('symbol', max_length=10, allow_special_chars=False)
def analyze_company():
    """Analyze company data using Gemini AI"""
    try:
        if not llm:
            return jsonify({'error': 'AI analysis service not available'}), 503
        
        data = request.json
        symbol = data.get('symbol')
        analysis_type = security_manager.validate_input(
            data.get('analysis_type', 'general'), 20, False
        )
        
        if analysis_type not in ['general', 'financial', 'risk']:
            return jsonify({'error': 'Invalid analysis type'}), 400
        
        # Validate API keys
        is_valid, message = security_manager.validate_api_key(FMP_API_KEY, 'Financial Modeling Prep')
        if not is_valid:
            return jsonify({'error': message}), 500
        
        # Gather company data with error handling
        company_data = {}
        
        # Get company profile
        try:
            profile_url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={FMP_API_KEY}"
            profile_response = requests.get(profile_url, timeout=10)
            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                if profile_data:
                    company_data['profile'] = profile_data[0]
        except requests.RequestException:
            pass  # Continue without profile data
        
        # Get latest financial statements
        try:
            income_url = f"https://financialmodelingprep.com/api/v3/income-statement/{symbol}?limit=2&apikey={FMP_API_KEY}"
            income_response = requests.get(income_url, timeout=10)
            if income_response.status_code == 200:
                company_data['income_statement'] = income_response.json()
        except requests.RequestException:
            pass  # Continue without financial data
        
        if not company_data:
            return jsonify({'error': 'Unable to fetch company data'}), 404
        
        # Create analysis prompt based on type
        if analysis_type == 'financial':
            system_prompt = """You are a financial analyst conducting due diligence for a potential acquisition. 
            Analyze the provided company data and provide insights on:
            1. Financial health and performance trends
            2. Revenue growth and profitability
            3. Key financial ratios and metrics
            4. Potential financial risks
            5. Investment attractiveness
            
            Provide a structured analysis with clear sections and actionable insights. Keep the analysis professional and objective."""
        elif analysis_type == 'risk':
            system_prompt = """You are a risk analyst conducting due diligence for a potential acquisition.
            Analyze the provided company data and identify:
            1. Business and operational risks
            2. Financial risks and red flags
            3. Market and competitive risks
            4. Regulatory and compliance risks
            5. Risk mitigation recommendations
            
            Provide a comprehensive risk assessment with severity levels. Be thorough but concise."""
        else:
            system_prompt = """You are a senior M&A analyst conducting comprehensive due diligence.
            Analyze the provided company data and provide:
            1. Executive summary of the company
            2. Key strengths and competitive advantages
            3. Areas of concern or weakness
            4. Market position and growth prospects
            5. Overall acquisition recommendation
            
            Provide a balanced and thorough analysis suitable for investment decision-making. Be professional and objective."""
        
        # Prepare data for analysis (sanitized)
        profile = company_data.get('profile', {})
        data_summary = f"""
        Company: {security_manager.validate_input(profile.get('companyName', symbol), 200)}
        Sector: {security_manager.validate_input(profile.get('sector', 'N/A'), 100)}
        Industry: {security_manager.validate_input(profile.get('industry', 'N/A'), 100)}
        Market Cap: ${profile.get('mktCap', 'N/A'):,} if isinstance(profile.get('mktCap'), (int, float)) else 'N/A'
        Description: {security_manager.validate_input(profile.get('description', 'N/A'), 500)}...
        
        Recent Financial Data:
        {json.dumps(company_data.get('income_statement', [])[:2], indent=2) if company_data.get('income_statement') else 'No financial data available'}
        """
        
        # Generate analysis using Gemini
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Please analyze the following company data:\n\n{data_summary}")
            ]
            
            response = llm.invoke(messages)
            analysis = response.content
            
            # Sanitize the analysis output
            analysis = security_manager.validate_input(analysis, 10000)
            
            return jsonify({
                'analysis': analysis,
                'company_data': company_data,
                'analysis_type': analysis_type
            })
        except Exception as e:
            security_manager.log_security_event('AI_ERROR', f'Gemini analysis failed: {str(e)}')
            return jsonify({'error': 'AI analysis service temporarily unavailable'}), 503
        
    except Exception as e:
        security_manager.log_security_event('ANALYSIS_ERROR', f'Unexpected error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@due_diligence_bp.route('/health', methods=['GET'])
@cross_origin()
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy', 
        'service': 'due-diligence-api',
        'security': 'enabled'
    })

