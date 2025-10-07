import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

export async function GET() {
  try {
    const dataDir = path.join(process.cwd(), '..', 'data');
    const directories = await fs.readdir(dataDir, { withFileTypes: true });

    const files = [];
    for (const dir of directories) {
      if (dir.isDirectory()) {
        const filePath = path.join(dataDir, dir.name, 'denoised_translated_results.json');
        try {
          await fs.access(filePath);
          files.push({
            id: dir.name,
            name: dir.name,
            path: filePath
          });
        } catch {
          // File doesn't exist, skip
        }
      }
    }

    return NextResponse.json({ files });
  } catch (error) {
    console.error('Error reading files:', error);
    return NextResponse.json({ error: 'Failed to read files' }, { status: 500 });
  }
}