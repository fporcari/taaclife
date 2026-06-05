# DEPLOY-HETZNER.md

Guida operativa per mettere NutriCoach in produzione su un server Hetzner con
dominio e HTTPS. Presuppone: server già attivo, accesso SSH, dimestichezza con
la riga di comando. Sostituisci `nutricoach.tuodominio.it` col tuo dominio e
`nutricoach` col nome scelto in Fase 0.

## Quadro generale
- L'app gira in un container Docker (immagine singola, costruita in Fase 0).
- Il database è un file SQLite su un volume Docker che persiste.
- I segreti (API key, JWT) stanno in un `.env` sul server, **fuori
  dall'immagine**.
- Un reverse proxy (Caddy) sta davanti e gestisce HTTPS in automatico via
  Let's Encrypt. Niente certificati da rinnovare a mano.

---

## 1. Prerequisiti sul server

Verifica/installa Docker:
```bash
docker --version || curl -fsSL https://get.docker.com | sh
```

Apri le porte 80 e 443 (firewall Hetzner Cloud dalla console, e ufw se attivo):
```bash
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
```

## 2. Punta il dominio

Nel pannello DNS del dominio, crea un record A che punta all'IP del server:
```
Tipo: A    Nome: nutricoach (o @)    Valore: <IP del server Hetzner>
```
Verifica la propagazione prima di procedere (HTTPS non parte senza DNS giusto):
```bash
dig +short nutricoach.tuodominio.it
```

## 3. Porta l'immagine sul server

Due strade.

**A) build sul tuo PC, trasferimento via SSH** (coerente con la Fase 0):
```bash
# sul PC, dopo ./build.sh
docker save nutricoach:latest | gzip | ssh utente@server 'gunzip | docker load'
```

**B) build direttamente sul server** (se preferisci):
```bash
# sul server, nella cartella del repo
./build.sh
```

## 4. Crea cartella di lavoro, volume ed `.env`

```bash
mkdir -p ~/nutricoach && cd ~/nutricoach
docker volume create nutricoach_data
```

Crea il file `.env` (NON committarlo, NON metterlo nell'immagine):
```bash
cat > .env <<'EOF'
DATABASE_URL=sqlite:////data/nutricoach.db
ANTHROPIC_API_KEY=sk-ant-...        # la tua chiave
COACH_MODEL=claude-haiku-4-5-20251001
JWT_SECRET=<stringa lunga casuale>
JWT_REFRESH_SECRET=<altra stringa lunga casuale>
EOF
chmod 600 .env
```
Genera i segreti JWT con:
```bash
openssl rand -hex 32
```

## 5. Avvia l'app

```bash
docker run -d --name nutricoach \
  --env-file .env \
  -v nutricoach_data:/data \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  nutricoach:latest
```
Note:
- `-p 127.0.0.1:8000:8000` espone l'app **solo in locale**: a Internet ci
  arriva attraverso Caddy, non direttamente. Più sicuro.
- `--restart unless-stopped`: riparte da sola dopo un reboot del server.
- Il volume su `/data` tiene il file SQLite tra un riavvio e l'altro.

Controlla che sia su:
```bash
docker logs -f nutricoach
```

## 6. Reverse proxy + HTTPS con Caddy

Caddy ottiene e rinnova i certificati da solo. Crea un `Caddyfile`:
```bash
cat > Caddyfile <<'EOF'
nutricoach.tuodominio.it {
    reverse_proxy 127.0.0.1:8000
}
EOF
```

Avvia Caddy in container, con accesso alla rete dell'host:
```bash
docker run -d --name caddy \
  --network host \
  -v $PWD/Caddyfile:/etc/caddy/Caddyfile \
  -v caddy_data:/data \
  -v caddy_config:/config \
  --restart unless-stopped \
  caddy:latest
```

Apri `https://nutricoach.tuodominio.it`: dovrebbe rispondere in HTTPS. La prima
volta Caddy impiega qualche secondo a emettere il certificato.

## 7. Verifica finale
- `https://...` carica e il lucchetto è valido.
- La chat coach risponde (se l'API key è giusta).
- Riavvia il server (`sudo reboot`) e controlla che app e Caddy ripartano da
  sole e che i dati ci siano ancora.

---

## Operazioni ricorrenti

**Aggiornare a una nuova immagine:**
```bash
# porta la nuova immagine (passo 3), poi:
docker stop nutricoach && docker rm nutricoach
# rilancia il docker run del passo 5
```
Il volume `nutricoach_data` resta, quindi i dati sopravvivono all'aggiornamento.

**Backup del database** (è un file solo):
```bash
docker run --rm -v nutricoach_data:/data -v $PWD:/backup alpine \
  cp /data/nutricoach.db /backup/nutricoach-$(date +%F).db
```
Conserva il backup fuori dal server. Per un backup sicuro a caldo si può usare
`sqlite3 .backup`, ma con poco traffico la copia del file va bene se l'app è
ferma un istante.

**Vedere i log:**
```bash
docker logs --tail 100 -f nutricoach
docker logs --tail 100 -f caddy
```

## Sicurezza minima
- `.env` con permessi `600`, mai committato.
- App esposta solo via Caddy, non direttamente su Internet.
- Considera `fail2ban` e disabilitazione del login SSH con password.
- Tieni Docker e il sistema aggiornati.
