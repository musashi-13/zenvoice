// src/server.ts
import express from 'express';
import dotenv from 'dotenv';
import path from 'path';
import testRoutes from './routes/test-routes';
import apiRoutes from './routes/api-routes';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 4000;

app.use(express.static(path.join(__dirname, '../public')));
app.use(express.json());

app.use('/health', testRoutes);
app.use('/api', apiRoutes);

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});