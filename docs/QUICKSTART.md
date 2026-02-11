# Quickstart

1. Install dependencies
```bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

2. Set API keys in `backend/.env.real`

3. Start dev servers
```bash
npm run dev
```

4. Open dashboard
- [http://localhost:5173](http://localhost:5173) (frontend dev)
- [http://localhost:8000](http://localhost:8000) (backend)
