// src/server.ts
import express from 'express';
import dotenv from 'dotenv';
import path from 'path';
import cors from 'cors';
import testRoutes from './routes/test-routes';
import apiRoutes from './routes/api-routes';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 4000;

app.use(cors(
    {
        origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
        methods: ['GET', 'POST', 'PUT', 'DELETE'],
        // credentials: true,
    }
));
app.use(express.static(path.join(__dirname, '../public')));
app.use(express.json());

app.use('/health', testRoutes);
app.use('/api', apiRoutes);

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});