import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, dash_table
import pandas as pd
import plotly.express as px
import yfinance as yf
import datetime

# --- Static Portfolio ---
portfolio = {
    'NVDA': {'shares': 100.012, 'cost_basis': 113.46},
    'CRM': {'shares': 29, 'cost_basis': 264.38},
    'SMCI': {'shares': 1, 'cost_basis': 30.00},
    'INTC': {'shares': 3, 'cost_basis': 20},
    'MSFT': {'shares': 0.015, 'cost_basis': 390.67},
    'META': {'shares': 0.002, 'cost_basis': 589.28},
    'AAPL': {'shares': 0.01, 'cost_basis': 243.59},
    'AMZN': {'shares': 5, 'cost_basis': 237},
    'GOOGL': {'shares': 28, 'cost_basis': 185.45},
}

# --- Functions ---
def get_portfolio_data():
    records = []
    total_value = 0
    for ticker, pos in portfolio.items():
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            fast = stock.fast_info
            price = fast['lastPrice']
            target = info.get('targetMeanPrice', None)
            pe = info.get('forwardPE', None)
            value = price * pos['shares']
            gain = (price - pos['cost_basis']) * pos['shares']
            total_value += value

            records.append({
                'Ticker': ticker,
                'Shares': round(pos['shares'], 4),
                'Cost Basis': round(pos['cost_basis'], 2),
                'Current Price': round(price, 2),
                'Value': round(value, 2),
                'Gain/Loss': round(gain, 2),
                'Target Price': round(target, 2) if target else 'N/A',
                'Forward P/E': round(pe, 2) if pe else 'N/A'
            })
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
    df = pd.DataFrame(records)
    return df, total_value

# --- App Setup ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.themes.DARKLY])
app.title = "Portfolio Growth Simulator"

app.layout = dbc.Container([
    html.Br(),
    html.H1("📈 Portfolio Growth Simulator", className="text-center mb-4 text-light"),

    dbc.Card([
        dbc.CardHeader("💼 Income & Raises", className="text-light"),
        dbc.CardBody([
            dbc.Label("Base Salary ($):", className="text-light"),
            dcc.Input(id='base-salary', type='number', value=250000, debounce=True, className="form-control"),
            html.Br(), html.Br(),
            dbc.Label("Bonus %:", className="text-light"),
            dcc.Slider(id='bonus-pct', min=0.0, max=1.0, step=0.01, value=0.40,
                       marks={i/10: f'{int(i*10)}%' for i in range(0, 11)}),
            html.Br(),
            dbc.Label("Bonus Tax Rate:", className="text-light"),
            dcc.Slider(id='bonus-tax', min=0.0, max=0.5, step=0.01, value=0.35,
                       marks={i/20: f'{int(i*5)}%' for i in range(0, 11)}),
            html.Br(),
            dbc.Label("Annual Raise %:", className="text-light"),
            dcc.Slider(id='raise-pct', min=0.0, max=0.1, step=0.01, value=0.04,
                       marks={i/100: f'{i}%' for i in range(0, 11)})
        ])
    ], className="mb-4"),

    dbc.Card([
        dbc.CardHeader("💰 Investment Assumptions", className="text-light"),
        dbc.CardBody([
            dbc.Label("Initial Monthly Investment:", className="text-light"),
            dcc.Input(id='monthly-investment', type='number', value=2000, debounce=True, className="form-control"),
            html.Br(), html.Br(),
            dbc.Label("Portfolio Growth Rate:", className="text-light"),
            dcc.Slider(id='growth-rate', min=0.0, max=0.30, step=0.01, value=0.15,
                       marks={i/100: f'{i}%' for i in range(0, 31, 5)}),
            html.Br(),
            dbc.Label("Years to Simulate:", className="text-light"),
            dcc.Slider(id='years', min=1, max=50, step=1, value=10,
                       marks={i: str(i) for i in range(1, 51, 5)})
        ])
    ], className="mb-5"),

    html.H2("📊 Projected Portfolio Value", className="text-center text-light"),
    dcc.Graph(id='portfolio-chart'),

    html.H2("📋 Year-by-Year Table", className="text-center text-light"),
    html.Div(id='portfolio-table', className="mb-5"),

    html.H2("💼 Current Portfolio Overview", className="text-center text-light"),
    dcc.Interval(id='refresh-interval', interval=10*60*1000, n_intervals=0),  # every 10 minutes
    dcc.Graph(id="portfolio-pie"),
    html.Div(id="portfolio-table-live", className="mb-5")
], fluid=True)

# --- Simulated Portfolio Growth Callback ---
@app.callback(
    [Output('portfolio-chart', 'figure'),
     Output('portfolio-table', 'children')],
    [Input('base-salary', 'value'),
     Input('bonus-pct', 'value'),
     Input('bonus-tax', 'value'),
     Input('raise-pct', 'value'),
     Input('monthly-investment', 'value'),
     Input('growth-rate', 'value'),
     Input('years', 'value')]
)
def update_projection(base_salary, bonus_pct, bonus_tax, raise_pct, monthly_investment, growth_rate, years):
    salary = base_salary
    portfolio_value = 0
    records = []

    for year in range(1, years + 1):
        annual_contribution = monthly_investment * 12
        after_tax_bonus = salary * bonus_pct * (1 - bonus_tax)
        total_invested = annual_contribution + after_tax_bonus
        portfolio_value = (portfolio_value + total_invested) * (1 + growth_rate)

        records.append({
            'Year': year,
            'Base Salary': round(salary, 2),
            'Monthly Investment': round(monthly_investment, 2),
            'Annual Contribution': round(annual_contribution, 2),
            'After-Tax Bonus': round(after_tax_bonus, 2),
            'Total Invested': round(total_invested, 2),
            'Portfolio Value': round(portfolio_value, 2)
        })

        salary *= (1 + raise_pct)
        monthly_investment += (base_salary * raise_pct) / 12

    df = pd.DataFrame(records)

    fig_chart = px.line(df, x='Year', y='Portfolio Value', markers=True,
                        title='Portfolio Value Over Time',
                        labels={'Portfolio Value': 'Portfolio ($)'})
    fig_chart.update_layout(template="plotly_dark", yaxis_tickprefix="$", font_color="white")

    table = dash_table.DataTable(
        columns=[{"name": i, "id": i} for i in df.columns],
        data=df.to_dict("records"),
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'center', 'backgroundColor': '#222', 'color': 'white'},
        style_header={'backgroundColor': '#111', 'fontWeight': 'bold'}
    )

    return fig_chart, table

# --- Live Portfolio Analytics Callback ---
@app.callback(
    [Output('portfolio-pie', 'figure'),
     Output('portfolio-table-live', 'children')],
    Input('refresh-interval', 'n_intervals')
)
def update_portfolio(_):
    df, total = get_portfolio_data()

    pie = px.pie(df, names='Ticker', values='Value', title='Allocation by Market Value')
    pie.update_layout(template="plotly_dark", font_color="white")

    table = dash_table.DataTable(
        columns=[{"name": i, "id": i} for i in df.columns],
        data=df.to_dict('records'),
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'center', 'backgroundColor': '#222', 'color': 'white'},
        style_header={'backgroundColor': '#111', 'fontWeight': 'bold'},
        style_data_conditional=[
            {'if': {'filter_query': '{Gain/Loss} > 0', 'column_id': 'Gain/Loss'},
             'color': 'lime'},
            {'if': {'filter_query': '{Gain/Loss} < 0', 'column_id': 'Gain/Loss'},
             'color': 'red'}
        ]
    )

    return pie, table

# --- Run Server ---
app.run(debug=True)