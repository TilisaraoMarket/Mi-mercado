# TechTrove Deployment Guide

This guide provides instructions for deploying the TechTrove application on Seenode Cloud.

## Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- Seenode Cloud account

## Deployment Steps

1. Create a new project on Seenode Cloud
2. Set up environment variables:
   - DATABASE_URL (PostgreSQL connection string)
   - MONGODB_URI (MongoDB connection string)
   - STRIPE_SECRET_KEY (for payments)

3. Push your code to GitHub
4. Connect your GitHub repository to Seenode Cloud
5. Deploy using the Seenode Cloud dashboard

## Environment Variables

The application requires the following environment variables:
- DATABASE_URL: postgresql://techtrove_user:techtrove_password@localhost:5432/techtrove_db
- PORT: 80
- SECRET_KEY: (dejar vacío)
- SESSION_LIFETIME_DAYS: 7
- stripe_secret_key: (dejar vacío)
- STRIPE_PUBLIC_KEY: (dejar vacío)

## Database Setup

The application uses PostgreSQL for all data storage

## Security

- Ensure sensitive data is stored in environment variables
- Use HTTPS for production deployments
- Regularly update dependencies
