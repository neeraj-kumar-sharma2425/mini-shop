# Mini Shop: Live Deploy Guide

Ye ek Flask e-commerce app hai: register/login, products, cart, checkout, aur order history.

## Folder structure

```
liveshop/
├── app.py              # Flask backend (sab API routes aur database)
├── templates/
│   └── index.html      # Frontend (HTML + CSS + JavaScript)
├── requirements.txt    # Python packages
├── Procfile            # Deploy start command
├── .gitignore
└── README.md
```

## 1. Local chalana (test ke liye)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Browser mein `http://127.0.0.1:5000` kholein.

## 2. GitHub par code daalna

1. GitHub par ek naya repository banayein (jaise `mini-shop`).
2. Is folder ko repository mein push karein:

```bash
git init
git add .
git commit -m "Mini shop app"
git branch -M main
git remote add origin https://github.com/<aapka-username>/mini-shop.git
git push -u origin main
```

## 3. Render par live karna (free)

1. [render.com](https://render.com) par account banayein aur GitHub se login karein.
2. **New → Web Service** chunein aur apna `mini-shop` repository select karein.
3. Settings:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
4. **Environment** mein ek variable add karein:
   - Key: `SECRET_KEY`
   - Value: koi lamba random text (jaise `python -c "import secrets; print(secrets.token_hex(32))"` ka output)
5. **Create Web Service** dabayein. Kuch minute mein aapko `https://mini-shop-xxxx.onrender.com` jaisa public link milega.

Ye link kisi ko bhi bhejein, wo shop khol kar register, login aur order kar sakta hai.

## 4. Railway par karna (vaikalpik)

1. [railway.app](https://railway.app) par GitHub se login karke **New Project → Deploy from GitHub repo** chunein.
2. Procfile apne aap pickup ho jati hai. Variables mein `SECRET_KEY` add karein.
3. **Settings → Networking → Generate Domain** dabayein, public link mil jayega.

## Zaroori baat: data kab tak save rahega

- App ka database ek SQLite file hai (`shop.db`).
- Render aur Railway ka free storage **restart ya redeploy par reset ho sakta hai**. Matlab users aur orders mit sakte hain.
- Demo ya testing ke liye ye theek hai. Real shop ke liye:
  - Platform par **persistent disk** add karein aur `DATABASE_PATH` ko us disk ke path par set karein, ya
  - Database ko **PostgreSQL** par shift karein (ye bada badlav hai, zaroorat ho to bataiye).

## Environment variables

| Variable        | Kaam                                                        |
|-----------------|-------------------------------------------------------------|
| `SECRET_KEY`    | Login session ko secure rakhta hai. Deploy par zaroor set karein. |
| `DATABASE_PATH` | Database file ka path. Default: `shop.db` (app ke folder mein). |
| `PORT`          | Platform khud deta hai. Local par default `5000`.           |

## Health check

`/health` URL `{"status": "ok"}` lautata hai. Deploy ke baad ye check karne ke liye kaam aata hai ki app chal raha hai.
