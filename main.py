from google.cloud import storage
from flask import Flask, jsonify, request
import numpy as np
import pandas as pd

app = Flask(__name__)


# Função para ler o arquivo do Google Cloud Storage
def ler_arquivo_gcs(bucket_name, blob_name):
    client = storage.Client.create_anonymous_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    conteudo = blob.download_as_string()
    return conteudo.decode("utf-8")


# Função para processar o conteúdo do arquivo e converter em DataFrame
def processar_conteudo(conteudo):
    conteudo = conteudo.replace('\r', '')
    lines = conteudo.strip().split('\n')
    data = [line.split(',') for line in lines]
    dados = pd.DataFrame(data[1:], columns=data[0])
    dados['PrecoAcao'] = dados['PrecoAcao'].astype(float)
    dados['Date'] = pd.to_datetime(dados['Date'], format='%d/%m/%Y')
    dados['Ticker'] = dados['Ticker'].astype(str)
    return dados


# Função para obter os dados do arquivo no GCS
def obter_dados(bucket_name, blob_name):
    conteudo_arquivo = ler_arquivo_gcs(bucket_name, blob_name)
    dados = processar_conteudo(conteudo_arquivo)
    return dados


# Função para calcular média e volatilidade dos retornos diários
def calcular_estatisticas_retorno(dados):
    retorno_diario = dados['PrecoAcao'].pct_change()
    media_retorno = retorno_diario.mean()
    volatilidade_retorno = retorno_diario.std()
    return media_retorno, volatilidade_retorno


# Função para realizar a simulação de Monte Carlo
def simulacao_monte_carlo(preco_atual, media_retorno, volatilidade_retorno, dias_simulacoes, num_simulacoes):
    simulacoes = np.zeros((num_simulacoes, dias_simulacoes))
    for i in range(num_simulacoes):
        preco = np.zeros(dias_simulacoes)
        preco[0] = preco_atual
        for dia in range(1, dias_simulacoes):
            retorno_diario = np.random.normal(media_retorno, volatilidade_retorno)
            preco[dia] = preco[dia - 1] * (1 + retorno_diario)
        simulacoes[i, :] = preco
    return simulacoes


# Rota para realizar simulação de Monte Carlo com dados do arquivo no GCS
@app.route('/storage', methods=['GET'])
def simular_monte_carlo():
    # Parâmetros da simulação
    ticker_simulacao = request.args.get('ticker_simulacao')
    dias_sim = int(request.args.get('dias_sim'))
    num_sim = int(request.args.get('num_sim'))

    # Nome do bucket e do arquivo no GCS
    bucket_name = 'precoacao-412114_cloudbuild'
    blob_name = 'precoAcoes.csv'

    # Obtendo os dados do arquivo no GCS
    dados = obter_dados(bucket_name, blob_name)

    # Filtrando os dados para o ticker especificado
    dados = dados[dados['Ticker'] == ticker_simulacao].sort_values("Date")

    # Calculando média e volatilidade dos retornos diários
    media_retorno, volatilidade_retorno = calcular_estatisticas_retorno(dados)

    # Obtendo o preço atual do ativo
    preco_atual = dados['PrecoAcao'].iloc[-1]

    # Realizando a simulação de Monte Carlo
    simulacoes = simulacao_monte_carlo(preco_atual, media_retorno, volatilidade_retorno, dias_sim, num_sim)

    # Calculando a média para cada dia
    media_por_dia = np.mean(simulacoes, axis=0)

    # Organizando os resultados em um formato JSON
    resultados_json = {
        "ticker": ticker_simulacao,
        "preco_atual": preco_atual,
        "dias_simulacoes": dias_sim,
        "num_simulacoes": num_sim,
        "estatisticas_retorno": {
            "media_retorno": media_retorno,
            "volatilidade_retorno": volatilidade_retorno
        },
        "simulacoes": [
            {"dia": dia + 1, "media": media} for dia, media in enumerate(media_por_dia)
        ]
    }

    return jsonify(resultados_json)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
