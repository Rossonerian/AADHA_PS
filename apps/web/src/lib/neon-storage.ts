import {
  Files,
  type Body,
  type DeleteOptions,
  type DownloadOptions,
  type OperationOptions,
  type StoredFile,
  type UploadOptions,
  type UploadResult,
  type UrlOptions,
} from "files-sdk";
import { neon, type NeonAdapter } from "files-sdk/neon";

export const DEFAULT_ASSETS_BUCKET = "assets";

const storageClients = new Map<string, Files<NeonAdapter>>();

export function isStorageConfigured(): boolean {
  return Boolean(
    process.env.AWS_ENDPOINT_URL_S3?.trim() &&
    process.env.AWS_REGION?.trim() &&
    process.env.AWS_ACCESS_KEY_ID?.trim() &&
    process.env.AWS_SECRET_ACCESS_KEY?.trim(),
  );
}

export function getStorageClient(bucket: string = DEFAULT_ASSETS_BUCKET): Files<NeonAdapter> {
  const existing = storageClients.get(bucket);
  if (existing) {
    return existing;
  }

  const client = new Files({
    adapter: neon({ bucket }),
  });

  storageClients.set(bucket, client);
  return client;
}

export async function uploadAsset(
  key: string,
  body: Body,
  opts?: Omit<UploadOptions, "condition"> & { bucket?: string },
): Promise<UploadResult> {
  const { bucket = DEFAULT_ASSETS_BUCKET, ...uploadOpts } = opts ?? {};
  return getStorageClient(bucket).upload(key, body, uploadOpts);
}

export async function downloadAsset(
  key: string,
  opts?: DownloadOptions & { bucket?: string },
): Promise<StoredFile> {
  const { bucket = DEFAULT_ASSETS_BUCKET, ...downloadOpts } = opts ?? {};
  return getStorageClient(bucket).download(key, downloadOpts);
}

export async function getAssetUrl(
  key: string,
  opts?: UrlOptions & { bucket?: string },
): Promise<string> {
  const { bucket = DEFAULT_ASSETS_BUCKET, ...urlOpts } = opts ?? {};
  return getStorageClient(bucket).url(key, urlOpts);
}

export async function assetExists(
  key: string,
  opts?: OperationOptions & { bucket?: string },
): Promise<boolean> {
  const { bucket = DEFAULT_ASSETS_BUCKET, ...existsOpts } = opts ?? {};
  return getStorageClient(bucket).exists(key, existsOpts);
}

export async function deleteAsset(
  key: string,
  opts?: DeleteOptions & { bucket?: string },
): Promise<void> {
  const { bucket = DEFAULT_ASSETS_BUCKET, ...deleteOpts } = opts ?? {};
  return getStorageClient(bucket).delete(key, deleteOpts);
}
