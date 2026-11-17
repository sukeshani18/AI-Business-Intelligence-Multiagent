# AI Business Intelligence Multi-Agent
An AI-powered Business Intelligence platform that transforms business datasets into meaningful insights using multi-agent analysis.

## Project Overview
AI Business Intelligence Multi-Agent helps users analyze business data through an interactive dashboard and AI-powered analysis workflow.
Users can upload a CSV dataset, explore key performance indicators and visualizations, and ask business-related questions to receive data-driven insights.

## Key Features
- **CSV Upload:** Upload business datasets for analysis.
- **Interactive Dashboard:** View dynamically calculated KPI cards.
- **Business Visualizations:** Explore customer-wise performance, product contribution, category performance, and date-wise trends.
- **Multi-Agent Analysis:** Uses specialized agents for data analysis and business insights.
- **AI Business Q&A:** Ask questions about uploaded business data.
- **PDF Report:** Export dashboard reports for documentation and sharing.

## Multi-Agent Architecture
The application uses LangGraph to coordinate the analysis workflow.
- **Data Analyst Agent:** Analyzes the uploaded dataset and identifies relevant data patterns.
- **Business Insight Agent:** Helps interpret analytical results and generate business-oriented insights.
- **LangGraph Workflow:** Coordinates the agent workflow.
- **FastAPI Backend:** Handles API requests and data processing.
- **Next.js Frontend:** Provides the interactive dashboard.

## Technology Stack
| Component | Technology |
|---|---|
| Programming Language | Python |
| Frontend | Next.js, TypeScript |
| Backend | FastAPI |
| Data Processing | Pandas |
| Agent Framework | LangGraph |
| LLM Integration | Groq |
| Styling | Tailwind CSS |
| Version Control | Git and GitHub |

## Dashboard Preview
### Dashboard Overview
![Dashboard Overview](screenshots/dashboard-overview.png)

### Business Analytics
![Business Analytics](screenshots/business-analytics.png)

### AI Business Insights
![AI Business Insights](screenshots/ai-business-insights.png)

## Project Structure
```text
AI-Business-Intelligence/
│
├── agents/
│   ├── business_insight.py
│   └── data_analyst.py
│
├── graph/
│   └── workflow.py
│
├── utils/
│   ├── data_loader.py
│   ├── data_summary.py
│   └── llm_client.py
│
├── frontend/
│   ├── app/
│   ├── package.json
│   └── ...
│
├── api.py
├── app.py
├── main.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Run Locally

### 1. Clone the repository
```bash
git clone https://github.com/YOUR-USERNAME/ai-business-intelligence-multiagent.git
cd ai-business-intelligence-multiagent
```

### 2. Set up the Python environment
```bash
python -m venv myenv
```

Activate it on Windows:
```powershell
.\myenv\Scripts\Activate.ps1
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Create a `.env` file in the project root and configure your Groq API key:

```env
GROQ_API_KEY=your_groq_api_key
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Never commit API keys or environment files to GitHub.

### 4. Start the backend
```bash
uvicorn api:app --reload --port 8000
```

Backend API documentation:
http://127.0.0.1:8000/docs

### 5. Start the frontend
Open another terminal:
```bash
cd frontend
npm install
npm run dev
```

Open:
http://localhost:3000

## Example Business Questions
- Which customers contribute the most to total sales?
- Which products generate the highest revenue?
- Which categories are underperforming?
- How are sales changing over time?
- What business opportunities can be identified from the dataset?

## Future Improvements
- More advanced customer segmentation.
- Additional business performance metrics.
- Expanded AI-driven recommendations.


---

**Note:** Results depend on the quality, structure, and columns available in the uploaded dataset.
