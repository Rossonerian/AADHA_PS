import { NextResponse } from "next/server";
import { getNeonAuthHandlers, isNeonAuthConfigured } from "@/lib/neon-auth";

type AuthRouteContext = {
  params: Promise<{ path: string[] }>;
};

type AuthHttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

export const dynamic = "force-dynamic";

function handle(
  method: AuthHttpMethod,
  request: Request,
  context: AuthRouteContext,
): Promise<Response> {
  if (!isNeonAuthConfigured()) {
    return Promise.resolve(
      NextResponse.json(
        {
          error: {
            code: "AUTH_NOT_CONFIGURED",
            message: "Neon Auth is not configured",
          },
        },
        {
          status: 503,
          headers: { "Cache-Control": "no-store" },
        },
      ),
    );
  }
  return getNeonAuthHandlers()[method](request, context);
}

export async function GET(request: Request, context: AuthRouteContext): Promise<Response> {
  return handle("GET", request, context);
}

export async function POST(request: Request, context: AuthRouteContext): Promise<Response> {
  return handle("POST", request, context);
}

export async function PUT(request: Request, context: AuthRouteContext): Promise<Response> {
  return handle("PUT", request, context);
}

export async function DELETE(request: Request, context: AuthRouteContext): Promise<Response> {
  return handle("DELETE", request, context);
}

export async function PATCH(request: Request, context: AuthRouteContext): Promise<Response> {
  return handle("PATCH", request, context);
}
