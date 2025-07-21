// src/api/s3.ts
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { Request, Response } from "express";
import dotenv from 'dotenv';
dotenv.config();

const s3Client = new S3Client({
  region: process.env.AWS_REGION || "eu-north-1",
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY || "",
    secretAccessKey: process.env.AWS_SECRET_KEY || "",
  },
});

export const generatePresignedDownloadUrl = async (req: Request, res: Response) => {
  console.log(`Processing s3_url: ${req.query.s3_url}`);
  const s3Url = req.query.s3_url as string;

  if (!s3Url || !s3Url.startsWith("s3://")) {
    return res.status(400).json({ error: "Invalid S3 URL format" });
  }

  try {
    // Parse S3 URL (e.g., s3://invoicestore-abcd/raw/2025/07/invoice.pdf)
    const urlParts = s3Url.replace("s3://", "").split("/");
    const bucketName = urlParts[0];
    const key = urlParts.slice(1).join("/");

    if (!bucketName || !key) {
      throw new Error("Unable to parse S3 bucket or key from URL");
    }

    // Generate presigned URL for downloading
    const command = new GetObjectCommand({
      Bucket: bucketName,
      Key: key,
    });

    const presignedUrl = await getSignedUrl(s3Client, command, {
      expiresIn: 3600, // URL valid for 1 hour
    });

    res.json({ presignedUrl });
  } catch (error) {
    console.error("Error generating presigned download URL:", error);
    res.status(500).json({ error: "Failed to generate presigned download URL" });
  }
};