# Thai Discord Shop Bot

## Overview

This project is a sophisticated Discord bot designed for managing a Thai e-commerce shop within Discord servers. The bot provides an interactive shopping experience with product catalog management, purchase flows, and transaction history tracking. It supports both traditional prefix commands and modern slash commands, with full Thai language localization.

## System Architecture

### Backend Architecture
- **Language**: Python 3.8+
- **Framework**: Discord.py library for bot functionality
- **Data Storage**: Hybrid approach supporting both JSON files and MongoDB
- **File Structure**: Modular design with separate modules for different functionalities
- **Configuration**: JSON-based configuration files for categories, countries, and bot settings

### Frontend Architecture
- **Interface**: Discord UI components (buttons, modals, embeds)
- **Interaction Model**: Event-driven architecture with Discord.py's interaction system
- **User Experience**: Interactive buttons for product selection and quantity input
- **Localization**: Full Thai language support with emoji-based product display

## Key Components

### Product Management System
- **Product Catalog**: JSON-based product storage organized by country and category
- **Categories**: 7 main categories (money, weapon, item, story, car, fashion, rentcar)
- **Country Support**: Multi-country inventory system (Thailand, Japan, USA, Korea, China)
- **Admin Controls**: Commands for adding, editing, and deleting products

### Shopping Interface
- **Interactive UI**: Button-based product selection with quantity modals
- **Cart System**: Multi-item cart functionality with real-time total calculation
- **Payment Flow**: QR code generation for payment processing
- **Purchase History**: JSON-based transaction logging with timestamps

### Database Layer
- **Primary Storage**: JSON files for offline capability
- **Optional MongoDB**: Database integration for scalability
- **Backup System**: Automatic fallback to JSON when MongoDB is unavailable
- **Data Models**: Structured data for products, history, categories, and configurations

### Command System
- **Dual Support**: Both prefix commands (!) and slash commands (/)
- **User Commands**: Shop browsing, product viewing, help system
- **Admin Commands**: Product management, configuration updates
- **Localization**: All commands and responses in Thai language

## Data Flow

### Shopping Process
1. User initiates shop command with optional category filter
2. Bot displays interactive product selection interface
3. User selects products and quantities through Discord UI
4. System calculates totals and generates payment QR code
5. Transaction is logged to history file/database
6. Thank you message is sent to user

### Product Management
1. Admin adds/edits products through commands
2. Data is validated and stored in appropriate category files
3. MongoDB sync occurs if database is available
4. Product catalog is updated for immediate availability

### Configuration Management
- Category settings loaded from `categories_config.json`
- Country mappings managed through `countries.json`
- QR code and thank you messages configurable via JSON files
- Target channel configuration for notifications

## External Dependencies

### Core Dependencies
- **discord.py**: Main bot framework for Discord API interaction
- **pymongo**: MongoDB database connectivity
- **python-dotenv**: Environment variable management
- **qrcode**: QR code generation for payments
- **pillow**: Image processing for QR codes

### Optional Dependencies
- **flask**: Web server for deployment monitoring
- **gunicorn**: WSGI server for production deployment
- **dnspython**: DNS resolution for MongoDB Atlas connections

### Third-party Services
- **Discord API**: Bot hosting and user interaction
- **MongoDB Atlas**: Optional cloud database storage
- **Render.com**: Deployment platform integration
- **Cloudflare**: CDN for QR code image hosting

## Deployment Strategy

### Local Development
- Environment variables for bot token and database connection
- JSON file fallback for offline development
- Python virtual environment for dependency isolation

### Production Deployment
- **Platform**: Render.com with automatic deployments
- **Configuration**: Environment variable-based configuration
- **Monitoring**: Built-in web server for health checks
- **Scaling**: Stateless design allows for horizontal scaling

### Database Strategy
- **Primary**: JSON files for reliability and simplicity
- **Secondary**: MongoDB for advanced features and scalability
- **Fallback**: Automatic switching to JSON when database is unavailable

## Changelog

- July 08, 2025. Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.