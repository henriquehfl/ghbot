# 🎶 GhBot — Bot de Música para Discord

Bot de música multiplataforma para Discord, feito em Python. Aceita links do **YouTube**, **Spotify**, **Deezer** e **SoundCloud**, com sistema de fila, controle de volume, loop e suporte a playlists.

## ✨ Funcionalidades

- 🎵 Reprodução de áudio de YouTube, Spotify, Deezer e SoundCloud
- 📋 Suporte a playlists do YouTube
- 📝 Sistema de fila com shuffle e remoção individual
- 🔊 Controle de volume em tempo real
- 🔁 Modo loop (repetir música atual)
- 💤 Desconexão automática por inatividade (5 min)
- 🎨 Mensagens com embeds estilizados

## 🛠️ Tecnologias

- **Python 3.12+**
- **discord.py** — Integração com a API do Discord
- **yt-dlp** — Extração de áudio de múltiplas plataformas
- **FFmpeg** — Processamento e streaming de áudio
- **Docker** — Containerização para deploy

## 📦 Comandos

| Comando | Descrição |
| :--- | :--- |
| `!play <link/pesquisa>` | Toca música do YouTube, Spotify, Deezer ou SoundCloud |
| `!pause` | Pausa a música |
| `!resume` | Retoma a música pausada |
| `!skip` | Pula para a próxima |
| `!stop` | Para tudo e limpa a fila |
| `!queue` | Mostra a fila de reprodução |
| `!shuffle` | Embaralha a fila |
| `!remove <nº>` | Remove uma música da fila |
| `!nowplaying` | Mostra a música atual |
| `!volume <0-100>` | Ajusta o volume |
| `!loop` | Liga/desliga repetição |
| `!join` | Entra no canal de voz |
| `!leave` | Desconecta o bot |
| `!ping` | Testa a latência |
| `!comandos` | Mostra a lista de comandos |

## 🚀 Como rodar localmente

```bash
# Clone o repositório
git clone https://github.com/henriquehfl/ghbot.git
cd ghbot

# Crie e ative o ambiente virtual
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # Linux/Mac

# Instale as dependências
pip install -r requirements.txt

# Configure o token do bot
# Crie um arquivo .env na raiz com:
# DISCORD_TOKEN=seu_token_aqui

# Rode o bot
python main.py
```

> ⚠️ **Pré-requisito:** É necessário ter o [FFmpeg](https://ffmpeg.org/download.html) instalado e no PATH do sistema.

## 🐳 Deploy com Docker

```bash
docker build -t ghbot .
docker run --env-file .env ghbot
```

## 📄 Licença

MIT
