import { getNeonAuthHandlers } from "@/lib/neon-auth";

type AuthRouteContext = {
  params: Promise<{ path: string[] }>;
};

export const dynamic = "force-dynamic";

export async function GET(request: Request, context: AuthRouteContext): Promise<Response> {
  return getNeonAuthHandlers().GET(request, context);
}

export async function POST(request: Request, context: AuthRouteContext): Promise<Response> {
  return getNeonAuthHandlers().POST(request, context);
}

export async function PUT(request: Request, context: AuthRouteContext): Promise<Response> {
  return getNeonAuthHandlers().PUT(request, context);
}

export async function DELETE(request: Request, context: AuthRouteContext): Promise<Response> {
  return getNeonAuthHandlers().DELETE(request, context);
}

export async function PATCH(request: Request, context: AuthRouteContext): Promise<Response> {
  return getNeonAuthHandlers().PATCH(request, context);
}
