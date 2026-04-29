import streamlit as st
from google.cloud import discoveryengine_v1alpha as discoveryengine
from google.oauth2 import service_account
import csv
import io

# ---- CONFIGURAZIONE ----
PROJECT_ID = "seo-ranker-494109"

st.set_page_config(page_title="SEO Reranker", page_icon="📊", layout="wide")

# ---- PASSWORD ----
if "autenticato" not in st.session_state:
    st.session_state.autenticato = False

if not st.session_state.autenticato:
    password = st.text_input("Password", type="password")
    if password == st.secrets["app_password"]:
        st.session_state.autenticato = True
        st.rerun()
    elif password:
        st.error("Password errata")
    st.stop()

st.title("📊 SEO Reranker — Google Ranking API")
st.markdown("Testa la pertinenza dei tuoi testi rispetto a una keyword")

# ---- CREDENZIALI dai Secrets ----
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)

# ---- INPUT KEYWORD ----
keyword = st.text_input("🔍 Keyword", placeholder="es. lampade interno")

# ---- NUMERO TESTI ----
n_testi = st.sidebar.slider("Numero massimo di testi", min_value=2, max_value=10, value=5)

# ---- INPUT TESTI ----
st.markdown("### Testi da testare")
st.caption("Aggiungi i testi. Lascia vuoti quelli che non usi.")

testi_input = []
for i in range(1, n_testi + 1):
    with st.expander(f"Testo {i}", expanded=(i <= 2)):
        col1, col2 = st.columns([1, 2])
        with col1:
            tid = st.text_input("ID", value=f"testo-{i}", key=f"id_{i}")
            title = st.text_input("Titolo", key=f"title_{i}")
        with col2:
            content = st.text_area("Contenuto", height=150, key=f"content_{i}")

        if content.strip():
            testi_input.append({"id": tid, "title": title, "content": content})

# ---- ANALISI ----
if st.button("🚀 Analizza pertinenza", type="primary"):

    if not keyword:
        st.error("Inserisci una keyword")
    elif len(testi_input) < 2:
        st.error("Inserisci almeno 2 testi da confrontare")
    else:
        with st.spinner("Analisi in corso..."):
            try:
                client = discoveryengine.RankServiceClient(credentials=credentials)
                ranking_config = client.ranking_config_path(
                    project=PROJECT_ID,
                    location="global",
                    ranking_config="default_ranking_config",
                )

                request = discoveryengine.RankRequest(
                    ranking_config=ranking_config,
                    model="semantic-ranker-512@latest",
                    top_n=len(testi_input),
                    query=keyword,
                    records=[
                        discoveryengine.RankingRecord(
                            id=t["id"],
                            title=t["title"],
                            content=t["content"],
                        )
                        for t in testi_input
                    ],
                )

                response = client.rank(request=request)

                # ---- RISULTATI ----
                st.markdown("---")
                st.markdown(f"### Risultati per: *{keyword}*")

                risultati = sorted(response.records, key=lambda x: x.score, reverse=True)
                score_max = risultati[0].score if risultati[0].score > 0 else 1

                rows_csv = []
                for i, record in enumerate(risultati):
                    medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i + 1}."
                    score_pct = record.score / score_max

                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"{medal} **{record.id}**")
                        st.progress(score_pct)
                    with col2:
                        st.metric(label="Score", value=f"{record.score:.4f}")
                    st.markdown("")

                    rows_csv.append(
                        {"posizione": i + 1, "id": record.id, "score": record.score}
                    )

                # ---- EXPORT CSV ----
                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=["posizione", "id", "score"])
                writer.writeheader()
                writer.writerows(rows_csv)
                csv_data = buf.getvalue()

                st.download_button(
                    label="⬇️ Scarica risultati CSV",
                    data=csv_data,
                    file_name=f"reranker_{keyword.replace(' ', '_')}.csv",
                    mime="text/csv",
                )

            except Exception as e:
                st.error(f"Errore: {e}")
