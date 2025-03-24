# Build stage
FROM --platform=$BUILDPLATFORM node:18-alpine as build

WORKDIR /app

# Copy package files
COPY frontend/package.json frontend/package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy source files
COPY frontend/ ./

# Set environment variables
ENV REACT_APP_API_URL=http://localhost:8000

# Build the application
RUN npm run build

# Production stage
FROM --platform=$TARGETPLATFORM nginx:alpine

# Copy build files from build stage
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx configuration
COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]