import { NextResponse } from 'next/server';
import { mockRules } from '@/src/data/mock-rules';
import { buildBootstrapPayload } from '@/src/lib/dashboard';

export async function GET() {
  return NextResponse.json(buildBootstrapPayload(mockRules));
}
