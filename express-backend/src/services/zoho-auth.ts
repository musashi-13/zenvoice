import axios from 'axios';
import fs from 'fs/promises';
import path from 'path';
import { URLSearchParams } from 'url';

// Define interfaces for our data structures
interface ZohoTokenData {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  expiry_time?: number; // We'll add this to track expiration
}

interface ZohoPurchaseOrder {
  purchaseorder_id: string;
  purchaseorder_number: string;
  line_items: any[];
  [key: string]: any; // Allow other properties
}

const TOKEN_FILE_PATH = path.join(__dirname, '..', '..', 'zoho_tokens.json');

/**
 * Manages Zoho OAuth2 authentication and token persistence.
 */
class ZohoAuthService {
  private clientId: string = process.env.ZOHO_CLIENT_ID!;
  private clientSecret: string = process.env.ZOHO_CLIENT_SECRET!;
  private tokenData: ZohoTokenData | null = null;
  private isRefreshing = false;

  constructor() {
    this.loadTokens();
  }

  private async loadTokens() {
    try {
      if ((await fs.stat(TOKEN_FILE_PATH)).isFile()) {
        const fileContent = await fs.readFile(TOKEN_FILE_PATH, 'utf-8');
        this.tokenData = JSON.parse(fileContent);
      }
    } catch (error) {
      console.log('Token file not found or invalid. A new one will be created.');
      this.tokenData = null;
    }
  }

  private async saveTokens() {
    if (this.tokenData) {
      await fs.writeFile(TOKEN_FILE_PATH, JSON.stringify(this.tokenData, null, 2));
    }
  }

  private isTokenExpired(): boolean {
    if (!this.tokenData || !this.tokenData.expiry_time) {
      return true;
    }
    // Check if token expires in the next 5 minutes (300 seconds)
    return Date.now() >= this.tokenData.expiry_time - 300 * 1000;
  }

  private async refreshTokens(): Promise<void> {
    if (!this.tokenData?.refresh_token) {
      throw new Error('No refresh token available. Please provide a ZOHO_AUTH_CODE.');
    }

    this.isRefreshing = true;
    try {
      const params = new URLSearchParams();
      params.append('grant_type', 'refresh_token');
      params.append('client_id', this.clientId);
      params.append('client_secret', this.clientSecret);
      params.append('refresh_token', this.tokenData.refresh_token);

      const response = await axios.post<ZohoTokenData>(
        'https://accounts.zoho.in/oauth/v2/token',
        params
      );

      this.tokenData = {
        ...this.tokenData, // Keep original refresh token if a new one isn't provided
        ...response.data,
        expiry_time: Date.now() + response.data.expires_in * 1000,
      };

      await this.saveTokens();
      console.log('Successfully refreshed Zoho access token.');
    } catch (error: any) {
      console.error('Failed to refresh Zoho token:', error.response?.data);
      throw new Error('Token refresh failed. A new auth code may be required.');
    } finally {
      this.isRefreshing = false;
    }
  }

  public async getAccessToken(): Promise<string> {
    while (this.isRefreshing) {
      // If a refresh is already in progress, wait for it to complete
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    if (this.isTokenExpired()) {
      await this.refreshTokens();
    }

    if (!this.tokenData?.access_token) {
      throw new Error('Failed to obtain a valid Zoho access token.');
    }

    return this.tokenData.access_token;
  }
}

/**
 * A client for interacting with the Zoho Books API.
 */
class ZohoApiService {
  private authService: ZohoAuthService;
  private baseUrl = `https://www.zohoapis.in/books/v3`;
  private organizationId: string = process.env.ZOHO_ORGANIZATION_ID!;

  constructor() {
    this.authService = new ZohoAuthService();
  }

  private async getHeaders() {
    const accessToken = await this.authService.getAccessToken();
    return {
      Authorization: `Zoho-oauthtoken ${accessToken}`,
      'Content-Type': 'application/json',
    };
  }

  async getPurchaseOrderDetailsByNumber(poNumber: string): Promise<ZohoPurchaseOrder | null> {
    try {
      const headers = await this.getHeaders();
      // First, get the PO ID from its number
      const searchResponse = await axios.get(`${this.baseUrl}/purchaseorders`, {
        headers,
        params: {
          purchaseorder_number: poNumber,
          organization_id: this.organizationId,
        },
      });

      const purchaseOrders = searchResponse.data?.purchaseorders;
      if (!purchaseOrders || purchaseOrders.length === 0) {
        console.warn(`No purchase order found for PO number: ${poNumber}`);
        return null;
      }
      const poId = purchaseOrders[0].purchaseorder_id;

      // Now, get the full details using the ID
      const detailsResponse = await axios.get(`${this.baseUrl}/purchaseorders/${poId}`, {
        headers,
        params: { organization_id: this.organizationId },
      });

      console.log(`Successfully fetched details for PO ${poNumber}`);
      return detailsResponse.data?.purchaseorder;

    } catch (error: any) {
      console.error(`Failed to fetch details for PO ${poNumber}:`, error.response?.data);
      return null;
    }
  }
}

// Export a singleton instance so the same auth state is shared across the app
export const zohoApiService = new ZohoApiService();