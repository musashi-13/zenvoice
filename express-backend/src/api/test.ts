// src/api/testApi.ts
import { Request, Response } from 'express';

import path from 'path';

export const getTest = (req: Request, res: Response) => {
  const response = {
    message: 'Server is live',
    timestamp: new Date().toISOString(),
  };
  res.json(response);
};

export const getLucky = (req: Request, res: Response) => {
  const filePath = path.join(__dirname, '../public/lucky.gif');
  res.sendFile(filePath, (err) => {
    if (err) {
        console.log('I\'m feeling lucky!')
      console.error('Error sending file:', err);
      res.status(404).json({ error: 'File not found' });
    }
  });
};