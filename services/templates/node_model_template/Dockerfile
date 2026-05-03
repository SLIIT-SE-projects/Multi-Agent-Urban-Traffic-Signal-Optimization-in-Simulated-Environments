# syntax=docker/dockerfile:1.6
FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY . .

ENV PORT=9000 \
    MODEL_NAME=researcher_template_node \
    AUTHOR=researcher

EXPOSE 9000

CMD ["node", "server.js"]
