FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY index.html tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts tailwind.config.ts postcss.config.cjs ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY infra/nginx/default.conf /etc/nginx/conf.d/default.conf
