"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScreenshotGallery } from "./screenshot-gallery";
import { ScreenshotUploader } from "./screenshot-uploader";

export function ScreenshotsSection({ tradeId }: { tradeId: string }) {
  return (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle>Captures d&apos;écran</CardTitle>
        <CardDescription>Avant, pendant et après le trade. Les fichiers sont privés.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <ScreenshotUploader tradeId={tradeId} />
        <ScreenshotGallery tradeId={tradeId} />
      </CardContent>
    </Card>
  );
}
