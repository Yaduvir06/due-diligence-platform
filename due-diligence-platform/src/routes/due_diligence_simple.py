from flask import Blueprint, jsonify, request
from flask_cors import cross_origin
import os
import requests
from dotenv import load_dotenv
import json
from src.security import security_manager, require_valid_input, validate_symbol_input

# Load environment variables
load_dotenv()

due_diligence_bp = Blueprint('due_diligence', __name__)

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

@due_diligence_bp.route('/analyze-company', methods=['POST'])
@cross_origin()
@security_manager.rate_limit(max_requests=5, window_minutes=1)
@require_valid_input('symbol', max_length=10, allow_special_chars=False)
def analyze_company():
    """Analyze company data (simplified version without AI)"""
    try:
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
        
        # Generate basic analysis without AI
        profile = company_data.get('profile', {})
        income_statements = company_data.get('income_statement', [])
        
        analysis = f"""
Due Diligence Analysis for {profile.get('companyName', symbol)}

COMPANY OVERVIEW:
- Symbol: {symbol}
- Sector: {profile.get('sector', 'N/A')}
- Industry: {profile.get('industry', 'N/A')}
- Market Cap: ${profile.get('mktCap', 'N/A'):,} if isinstance(profile.get('mktCap'), (int, float)) else 'N/A'
- Employees: {profile.get('fullTimeEmployees', 'N/A'):,} if isinstance(profile.get('fullTimeEmployees'), (int, float)) else 'N/A'

FINANCIAL HIGHLIGHTS:
"""
        
        if income_statements and len(income_statements) >= 2:
            latest = income_statements[0]
            previous = income_statements[1]
            
            revenue_latest = latest.get('revenue', 0)
            revenue_previous = previous.get('revenue', 0)
            
            if revenue_previous > 0:
                revenue_growth = ((revenue_latest - revenue_previous) / revenue_previous) * 100
                analysis += f"- Revenue Growth: {revenue_growth:.1f}%\n"
            
            analysis += f"- Latest Revenue: ${revenue_latest:,} if isinstance(revenue_latest, (int, float)) else 'N/A'\n"
            analysis += f"- Net Income: ${latest.get('netIncome', 'N/A'):,} if isinstance(latest.get('netIncome'), (int, float)) else 'N/A'\n"
            analysis += f"- Gross Profit: ${latest.get('grossProfit', 'N/A'):,} if isinstance(latest.get('grossProfit'), (int, float)) else 'N/A'\n"
        
        if analysis_type == 'risk':
            analysis += """
RISK ASSESSMENT:
- Market Risk: Evaluate sector volatility and competitive position
- Financial Risk: Review debt levels and cash flow stability
- Operational Risk: Assess business model sustainability
- Regulatory Risk: Consider industry-specific regulations

Note: For detailed AI-powered analysis, please configure the Gemini API key.
"""
        elif analysis_type == 'financial':
            analysis += """
FINANCIAL ANALYSIS:
- Review revenue trends and growth patterns
- Analyze profitability margins and efficiency ratios
- Evaluate balance sheet strength and liquidity
- Assess cash flow generation and capital allocation

Note: For detailed AI-powered analysis, please configure the Gemini API key.
"""
        else:
            analysis += """
GENERAL ASSESSMENT:
- Strong market position in the technology sector
- Consistent revenue growth and profitability
- Well-established brand and customer base
- Consider competitive landscape and future growth prospects

Note: For detailed AI-powered analysis, please configure the Gemini API key.
"""
        
        return jsonify({
            'analysis': analysis,
            'company_data': company_data,
            'analysis_type': analysis_type,
            'note': 'This is a basic analysis. For AI-powered insights, configure the Gemini API key.'
        })
        
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
        'security': 'enabled',
        'version': 'simplified'
    })

