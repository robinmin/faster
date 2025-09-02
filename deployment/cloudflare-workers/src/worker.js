/**
 * Cloudflare Workers entry point for the Faster FastAPI application
 */

import { createApp } from '../../../main.py';

// Polyfill for Node.js compatibility
import { Buffer } from 'node:buffer';
global.Buffer = Buffer;

let app = null;

async function initializeApp(env) {
  if (app === null) {
    // Set environment variables from Cloudflare Workers
    process.env.ENVIRONMENT = env.ENVIRONMENT || 'production';
    process.env.DEPLOYMENT_PLATFORM = 'cloudflare-workers';
    process.env.CF_WORKERS_KV_NAMESPACE = env.CACHE ? 'CACHE' : null;
    process.env.CF_WORKERS_D1_DATABASE = env.DB ? 'DB' : null;
    
    // Import and initialize the FastAPI app
    const { default: fastAPIApp } = await import('../../../main.py');
    app = fastAPIApp;
  }
  return app;
}

export default {
  async fetch(request, env, ctx) {
    try {
      const app = await initializeApp(env);
      
      // Convert Cloudflare Workers Request to ASGI-compatible format
      const asgiRequest = await convertRequest(request, env);
      
      // Process the request through FastAPI
      const response = await app(asgiRequest);
      
      return convertResponse(response);
    } catch (error) {
      console.error('Worker error:', error);
      return new Response('Internal Server Error', {
        status: 500,
        headers: {
          'Content-Type': 'text/plain',
        },
      });
    }
  },
};

async function convertRequest(request, env) {
  const url = new URL(request.url);
  const body = await request.arrayBuffer();
  
  return {
    type: 'http',
    asgi: { version: '3.0' },
    http_version: '1.1',
    method: request.method,
    path: url.pathname,
    query_string: new TextEncoder().encode(url.search.slice(1)),
    headers: Array.from(request.headers.entries()).map(([name, value]) => [
      name.toLowerCase().replace(/-/g, '_'),
      value,
    ]),
    body: new Uint8Array(body),
    server: ['cloudflare-workers', 443],
    client: [request.headers.get('CF-Connecting-IP') || '127.0.0.1', 0],
  };
}

function convertResponse(asgiResponse) {
  const headers = new Headers();
  
  if (asgiResponse.headers) {
    asgiResponse.headers.forEach(([name, value]) => {
      headers.append(name, value);
    });
  }
  
  return new Response(asgiResponse.body, {
    status: asgiResponse.status || 200,
    headers: headers,
  });
}