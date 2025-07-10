// src/server.ts
import express from 'express';
import dotenv from 'dotenv';
import path from 'path';
import testRoutes from './routes/test-routes';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 4000;

app.use(express.static(path.join(__dirname, '../public')));
app.use(express.json());
app.use('/api', testRoutes);

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});