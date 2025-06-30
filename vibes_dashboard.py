import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output
import requests
from bs4 import BeautifulSoup

# --- Real Breadth Factor from Finviz ---
def get_breadth_factor():
    try:
        url = "https://finviz.com/screener.ashx?v=152&f=idx_sp500,sh_avg50_pa&ft=4"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        count_text = soup.find("td", class_="count-text")
        if not count_text: raise Exception("Breadth text not found")
        count = int(count_text.text.split("Total:")[1].split()[0])
        breadth_pct = count / 500
        return min(max(breadth_pct, 0), 1.0)
    except Exception as e:
        print(f"[Breadth Error] {e}")
        return 0.5

# --- Reddit & Finviz Sentiment ---
def get_sentiment_scores(ticker):
    try:
        reddit_url = f"https://apewisdom.io/stocks/{ticker.lower()}/"
        r = requests.get(reddit_url, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        mentions = soup.select_one('td[data-title="Mentions"]')
        reddit_score = min(1.0, int(mentions.text.replace(',', '')) / 1000) if mentions else 0.5
    except Exception as e:
        print(f"[Reddit Error] {e}")
        reddit_score = 0.5

    try:
        finviz_url = f"https://finviz.com/quote.ashx?t={ticker.lower()}"
        r = requests.get(finviz_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        news_table = soup.find("table", class_="fullview-news-outer")
        sentiment_score = 0.5
        if news_table:
            headlines = [row.a.text for row in news_table.find_all("tr")]
            pos = sum("upgrade" in h.lower() or "beats" in h.lower() for h in headlines)
            neg = sum("downgrade" in h.lower() or "misses" in h.lower() for h in headlines)
            sentiment_score = pos / (pos + neg + 1)
    except Exception as e:
        print(f"[Finviz Error] {e}")
        sentiment_score = 0.5

    return reddit_score, sentiment_score

# --- VIBES Calculation ---
def calculate_vibes(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="6mo")
    if hist.empty:
        return None, "No historical data found"

    today = hist.index[-1]

    # Volume
    avg_vol = hist['Volume'][-20:].mean()
    vol_score = hist['Volume'][-1] / avg_vol if avg_vol else 0
    vol_factor = min(vol_score / 2, 1.0)

    # Volatility (IV or fallback to historical)
    try:
        options = stock.option_chain()
        all_ivs = pd.concat([
            options.calls['impliedVolatility'].dropna(),
            options.puts['impliedVolatility'].dropna()
        ])
        iv_score = all_ivs.mean() * 100
        if np.isnan(iv_score): raise ValueError("IV score is NaN")
    except Exception as e:
        print(f"[Volatility Error] {e}")
        hl_range = (hist['High'] - hist['Low']) / hist['Close']
        iv_score = hl_range.rolling(5).mean().iloc[-1] * 100
    iv_factor = min(iv_score / 5, 1.0)

    # Earnings
    earnings_factor = 0.5
    try:
        cal = stock.calendar
        if isinstance(cal, pd.DataFrame) and 'Earnings Date' in cal.index:
            earnings_date = pd.to_datetime(cal.loc['Earnings Date'].values[0])
            if pd.notnull(earnings_date):
                days_to_earnings = (earnings_date - today).days
                earnings_factor = max(0, 10 - abs(days_to_earnings)) / 10
    except Exception as e:
        print(f"[Earnings Error] {e}")

    # Breadth
    breadth_factor = get_breadth_factor()

    # Sentiment
    reddit_score, finviz_score = get_sentiment_scores(ticker)
    sentiment_factor = (reddit_score + finviz_score) / 2

    # Final VIBES score
    vibes = (vol_factor + iv_factor + earnings_factor + breadth_factor + sentiment_factor) / 5
    signal = "🚀 Bullish" if vibes > 0.65 else "😐 Neutral" if vibes > 0.4 else "🔻 Bearish"

    print(f"\nVIBES for {ticker.upper()} as of {today.date()}")
    print(f"Volume Factor:      {vol_factor:.2f}")
    print(f"Volatility Factor:  {iv_factor:.2f}")
    print(f"Earnings Factor:    {earnings_factor:.2f}")
    print(f"Breadth Factor:     {breadth_factor:.2f}")
    print(f"Sentiment Factor:   {sentiment_factor:.2f}")
    print(f"\n✅ Final VIBES Score: {vibes:.2f} → {signal}")

    factors = {
        "Volume": vol_factor,
        "Volatility": iv_factor,
        "Earnings": earnings_factor,
        "Breadth": breadth_factor,
        "Sentiment": sentiment_factor
    }

    return {
        "ticker": ticker.upper(),
        "date": today.date(),
        "factors": factors,
        "vibes_score": vibes,
        "signal": signal
    }, None

# --- Dash Web App ---
app = Dash(__name__)
app.title = "VIBES Dashboard"
app.layout = html.Div([
    html.H1("📊 VIBES Indicator Dashboard"),
    html.Label("Enter Stock Ticker:"),
    dcc.Input(id="ticker-input", value="NVDA", type="text"),
    html.Br(), html.Br(),
    html.Div(id="output"),
    dcc.Graph(id="vibes-bar"),
    dcc.Graph(id="vibes-history")
])

# --- History Data Store ---
vibes_history_data = {}

@app.callback(
    Output("output", "children"),
    Output("vibes-bar", "figure"),
    Output("vibes-history", "figure"),
    Input("ticker-input", "value")
)
def update_dashboard(ticker):
    result, error = calculate_vibes(ticker)
    if error:
        return error, go.Figure(), go.Figure()

    today_str = str(result["date"])
    ticker = result["ticker"]
    vibes_score = result["vibes_score"]
    signal = result["signal"]
    factors = result["factors"]

    # Save VIBES history
    if ticker not in vibes_history_data:
        vibes_history_data[ticker] = []
    vibes_history_data[ticker].append((today_str, vibes_score))

    # Bar chart of current factors
    bar_fig = go.Figure(go.Bar(
        x=list(factors.keys()),
        y=list(factors.values()),
        marker_color='skyblue'
    ))
    bar_fig.update_layout(title=f"VIBES Breakdown for {ticker} → {signal}", yaxis=dict(range=[0, 1]))

    # Historical VIBES trend
    df_hist = pd.DataFrame(vibes_history_data[ticker], columns=["Date", "VIBES"])
    hist_fig = go.Figure(go.Scatter(
        x=df_hist["Date"],
        y=df_hist["VIBES"],
        mode='lines+markers',
        line=dict(shape='spline', width=3)
    ))
    hist_fig.update_layout(title=f"📈 VIBES Trend for {ticker}", yaxis=dict(range=[0, 1]))

    return (
        html.Div([
            html.P(f"✅ VIBES Score: {vibes_score:.2f} → {signal}"),
            html.Ul([html.Li(f"{k} Factor: {v:.2f}") for k, v in factors.items()])
        ]),
        bar_fig,
        hist_fig
    )

if __name__ == "__main__":
    app.run(debug=True)