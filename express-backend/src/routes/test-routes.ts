import { Router } from 'express';
import { getTest, getLucky } from '../api/test';

const router = Router();

router.get('/test', getTest);
router.get('/lucky', getLucky);          

export default router;