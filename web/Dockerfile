# Bull vs Bear frontend — build with Vite, serve static with nginx on Cloud Run.
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# The API base must be known at build time (baked into the static bundle).
ARG VITE_API_BASE=http://localhost:8000
ARG VITE_PHOENIX_URL=http://localhost:6006
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_PHOENIX_URL=$VITE_PHOENIX_URL
RUN npm run build

FROM nginx:1.27-alpine
# The nginx image substitutes ${PORT} into templates at startup (envsubst).
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV PORT=8080
EXPOSE 8080
