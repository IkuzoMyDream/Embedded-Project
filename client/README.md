This folder contains a React client for the Smart Dispense project.

Development:
1. cd client
2. npm install
3. npm start  # starts react dev server on 3000 and proxies API requests to Flask 5000

Production build:
1. npm run build
2. Copy the contents of client/build into server's static folder or run Flask which will serve from client/build automatically if present.
