🎵 Discord Music Bot

Um bot de música para Discord simples, rápido e eficiente, desenvolvido para reproduzir áudio diretamente em canais de voz com alta qualidade e estabilidade.

🚀 Sobre o projeto

Este bot foi criado com o objetivo de fornecer uma experiência prática e sem complicações para reprodução de músicas no Discord. Ele suporta comandos diretos, conexão automática em canais de voz e gerenciamento básico de reprodução.

⚡ Principais recursos
▶️ Reprodução de músicas via comando
⏸️ Pausar e retomar músicas
⏭️ Pular faixas
🔊 Controle de volume
🔁 Fila de reprodução
🔌 Conexão automática ao canal de voz
🎯 Objetivo

Facilitar o uso de música em servidores Discord sem depender de bots externos instáveis ou limitados, garantindo maior controle e personalização.

🧠 Tecnologias utilizadas
Python
Discord API
FFmpeg
Opus (codec de áudio)
📌 Observação

Este projeto é focado em simplicidade e eficiência. Ideal para uso pessoal ou em servidores privados.

💡 Consulte a documentação técnica abaixo para instruções de instalação e uso.

📃 Documentação (Funciona perfeitamente no Ubuntu 24.04):

# ⚙️ Instalação do Bot de Música Discord

Siga os passos abaixo para instalar e rodar o bot corretamente no seu servidor Linux.

---

## 📦 1. Instalar dependências

Copie e execute:

```bash
apt update
apt install python3 -y
apt install python3-venv -y
apt install libopus0 -y
apt install ffmpeg -y
```

---

## 🐍 2. Criar ambiente virtual

Faça Donwload dos seguintes arquivos: "cogs", "bot.py" e "requirements.txt".

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 📥 3. Instalar dependências do projeto

```bash
pip install -r requirements.txt
```

---

## 🔐 4. Criar arquivo `.env`

```bash
nano .env
```

Conteúdo:

```env
DISCORD_TOKEN=SEU_TOKEN_AQUI
MUSIC_CHANNEL_ID=ID_DO_CANAL_AQUI
```

---

## ▶️ 5. Rodar o bot (teste)

```bash
python3 bot.py
```

---

## ⚡ 6. Criar serviço (rodar 24/7)

Crie o arquivo:

```bash
nano /etc/systemd/system/botdiscord.service
```

Conteúdo:

```ini
[Unit]
Description=Bot Discord
After=network.target

[Service]
User=root
WorkingDirectory=/BotDiscord

EnvironmentFile=/BotDiscord/.env
Environment="PATH=/BotDiscord/venv/bin:/usr/bin:/bin"

ExecStart=/BotDiscord/venv/bin/python /BotDiscord/bot.py

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

---

## 🔄 7. Ativar serviço

```bash
systemctl daemon-reexec
systemctl daemon-reload
systemctl enable botdiscord
systemctl start botdiscord
```

Ver status:

```bash
systemctl status botdiscord
```

---

# 🤖 Criar o Bot no Discord

1. Acesse:
   👉 https://discord.com/developers/applications

2. Clique em **New Application**

3. Vá em **Bot → Add Bot**

4. Copie o **TOKEN** e coloque no `.env`

5. Em **Privileged Gateway Intents**, ative:

* MESSAGE CONTENT INTENT

---

## 🔗 Convidar o bot para o servidor

1. Vá em **OAuth2 → URL Generator**
2. Marque:

   * `bot`
3. Permissões:

   * Administrator (ou as que preferir)
4. Acesse o link gerado e adicione ao servidor

---

# 🆔 Como pegar o ID do canal

No Discord:

1. Vá em **Configurações (⚙️) → Avançado**
2. Ative **Modo Desenvolvedor**
3. Clique com botão direito no canal
4. Clique em **Copiar ID**

Cole no `.env`:

```env
MUSIC_CHANNEL_ID=123456789
```

---

## ✅ Pronto!

Seu bot estará rodando automaticamente e pronto para tocar músicas 🎵
