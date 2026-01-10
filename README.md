# Compliment Bot 🤖💝

A Telegram bot that generates funny, personalized compliments based on recent news headlines using AI. Start your day with a smile by receiving unique compliments that are both entertaining and current!

## 🌟 Features

- **AI-Powered Compliments**: Uses OpenAI's GPT models to generate creative compliments based on recent news
- **Daily News Integration**: Fetches fresh headlines from NewsAPI to create contextually relevant compliments
- **Telegram Bot Interface**: Easy-to-use commands for starting, stopping, and getting help
- **Persistent Storage**: Stores generated compliments in a PostgreSQL database to avoid duplicates
- **Configurable**: All settings can be customized through `config.yaml`
- **Scheduled Generation**: Automatically generates new compliments at configurable intervals
- **Fallback System**: Provides default compliments when news or AI services are unavailable

## 🚀 How It Works

1. **News Retrieval**: The bot fetches recent headlines from configured news sources
2. **AI Processing**: Each headline is processed by an AI model to generate a funny compliment
3. **Selection**: The best compliment is selected from multiple generated options
4. **Storage**: The compliment is stored in the database for the day
5. **Delivery**: Users receive the compliment when they interact with the bot

## 📋 Prerequisites

- Python 3.11+
- OpenAI API key
- NewsAPI key
- Telegram Bot Token

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd compliment_of_the_day
   ```

2. **Install dependencies**:
   ```bash
   pip install -e .
   # or using uv
   uv sync
   ```

3. **Set up environment variables**:
   Create a `.env` file in the project root:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   NEWSAPI_API_KEY=your_newsapi_key_here
   TG_BOT_TOKEN=your_telegram_bot_token_here
   DATABASE_URL=postgresql://user:password@host:port/database
   ```
   
   **Note**: If deploying to Railway.com, the `DATABASE_URL` is automatically provided by Railway. For local development, you can use a local PostgreSQL instance or a service like Railway, Supabase, or Neon.

4. **Configure the bot** (optional):
   Edit `config.yaml` to customize news sources, AI model settings, and bot messages.

## 🎮 Usage

### Running the Bot

```bash
python tg_bot.py
```

### Telegram Commands

- `/start` - Start receiving compliments (sends a compliment every 24 hours by default)
- `/stop` - Stop the bot
- `/help` - Show help message

### Manual Compliment Generation

You can also generate compliments manually:

```python
from compliment import ComplimentGenerator
from news import FreshHeadlinesRetriever
from setup import setup_application

setup_application()
news_client = FreshHeadlinesRetriever()
generator = ComplimentGenerator(news_client)
compliment = generator.generate_compliment_for_date(datetime.now().date())
print(compliment)
```

## ⚙️ Configuration

The `config.yaml` file allows you to customize:

### News Settings
```yaml
news:
  sources: ["the-verge"]  # News sources to fetch from
  page_size: 10           # Number of articles to fetch
  sort_by: "popularity"   # Sort order
  language: "en"          # Language
  query: "News"           # Search query
  from_days: 7            # How many days back to search
```

### AI Model Settings
```yaml
llm:
  model: "gpt-4o-mini"    # OpenAI model to use
  temperature: 0.7        # Creativity level (0-1)
  max_retries: 3          # Retry attempts
```

### Telegram Bot Settings
```yaml
telegram:
  messages:
    start: "Your custom start message"
    help: "Your custom help message"
    # ... other messages
  jobs:
    compliment_hour: 9
    compliment_minute: 0
    generate_hour: 0
    generate_minute: 0
    first_run_delay: 10
```

### Database Settings
```yaml
database:
  type: "postgresql"      # Database type (PostgreSQL)
```

**Note**: The database connection is configured via the `DATABASE_URL` environment variable. The connection string format is:
```
postgresql://username:password@host:port/database
```

When deploying to Railway.com, the `DATABASE_URL` is automatically set by Railway.

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Telegram Bot  │    │  Compliment      │    │   News API      │
│                 │◄──►│  Generator       │◄──►│                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Database      │    │   OpenAI API     │    │   Config        │
│   Manager       │    │   (GPT Models)   │    │   System        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Key Components

- **`tg_bot.py`**: Main Telegram bot with command handlers and job scheduling
- **`compliment.py`**: AI-powered compliment generation using LangChain
- **`news.py`**: News headline retrieval from NewsAPI
- **`database.py`**: PostgreSQL database management for storing compliments
- **`setup.py`**: Centralized configuration and logging setup
- **`config.yaml`**: Configuration file for all customizable settings

## 🔧 Development

### Project Structure
```
compliment_of_the_day/
├── compliment.py      # Compliment generation logic
├── config.yaml        # Configuration file
├── database.py        # Database operations
├── news.py           # News API integration
├── setup.py          # Setup and configuration management
├── tg_bot.py         # Telegram bot implementation
├── pyproject.toml    # Project dependencies
└── README.md         # This file
```

### Adding New Features

1. **New News Sources**: Add to `config.yaml` under `news.sources`
2. **Custom Prompts**: Modify `prompts` section in `config.yaml`
3. **Database Schema**: Update `Compliment` model in `database.py`
4. **Bot Commands**: Add new handlers in `tg_bot.py`

### Testing

```bash
# Test compliment generation
python -c "
from compliment import ComplimentGenerator
from news import FreshHeadlinesRetriever
from setup import setup_application
from datetime import datetime

setup_application()
news_client = FreshHeadlinesRetriever()
generator = ComplimentGenerator(news_client)
compliment = generator.generate_compliment_for_date(datetime.now().date())
print(f'Generated: {compliment}')
"
```

## 🐛 Troubleshooting

### Common Issues

1. **"No compliments generated"**
   - Check OpenAI API key and quota
   - Verify NewsAPI key and rate limits
   - Check internet connectivity

2. **"Bot not responding"**
   - Verify Telegram bot token
   - Check if bot is running (`/start` command)
   - Review logs for errors

3. **"Database errors"**
   - Verify `DATABASE_URL` environment variable is set correctly
   - Check PostgreSQL connection credentials and network access
   - Ensure the database exists and the user has proper permissions
   - For Railway.com deployments, verify the database service is running

### Logs

The bot logs all activities with timestamps. Check the console output for detailed error messages and debugging information.

## 📝 License

This project is open source. Feel free to use, modify, and distribute according to your needs.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## 🙏 Acknowledgments

- OpenAI for providing the AI models
- NewsAPI for news data
- python-telegram-bot for the Telegram integration
- LangChain for AI workflow management

---

**Made with ❤️ to spread positivity and smiles!**
