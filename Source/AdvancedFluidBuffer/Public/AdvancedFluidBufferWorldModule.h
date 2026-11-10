#pragma once

#include "CoreMinimal.h"
#include "Module/GameWorldModule.h"
#include "AdvancedFluidBufferWorldModule.generated.h"

class UFGRecipe;
class UFGSchematic;

/**
 * Unlocks the Advanced Fluid Buffer together with the Industrial Fluid Buffer.
 *
 * Rather than hardcoding which milestone that is, it searches every schematic for the one that
 * unlocks Recipe_IndustrialTank and adds this mod's recipe to the same unlock. The patch is on
 * the schematic's class default object, so the HUB lists the new building and buying the
 * milestone grants it. Saves that already own that milestone get the recipe directly.
 */
UCLASS()
class ADVANCEDFLUIDBUFFER_API UAdvancedFluidBufferWorldModule : public UGameWorldModule
{
	GENERATED_BODY()

public:
	UAdvancedFluidBufferWorldModule();

	virtual void DispatchLifecycleEvent(ELifecyclePhase phase) override;

private:
	/** Returns the schematic that unlocks the Industrial Fluid Buffer, after adding our recipe to it. */
	TSubclassOf<UFGSchematic> PatchIndustrialTankSchematic();

	/** Kept referenced so the loaded classes are not garbage collected. */
	UPROPERTY()
	TSubclassOf<UFGRecipe> mRecipe;

	UPROPERTY()
	TSubclassOf<UFGRecipe> mIndustrialTankRecipe;
};
