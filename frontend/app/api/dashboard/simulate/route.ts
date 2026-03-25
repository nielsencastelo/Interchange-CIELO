import { NextRequest, NextResponse } from 'next/server';
import { mockRules } from '@/src/data/mock-rules';
import { compareNetworks, simulateRules } from '@/src/lib/dashboard';
import { SimulationInput } from '@/src/types/interchange';

export async function POST(request: NextRequest) {
  const body = (await request.json()) as SimulationInput;
  const result = simulateRules(mockRules, body);
  const comparison = compareNetworks(mockRules, body);

  return NextResponse.json({ result, comparison });
}
