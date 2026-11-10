#include "AdvancedFluidBufferWorldModule.h"

#include "AdvancedFluidBuffer.h"
#include "FGRecipe.h"
#include "FGRecipeManager.h"
#include "FGSchematic.h"
#include "FGSchematicManager.h"
#include "Unlocks/FGUnlockRecipe.h"

static const TCHAR* RecipePath = TEXT("/AdvancedFluidBuffer/Recipe_AdvancedFluidBuffer.Recipe_AdvancedFluidBuffer_C");
static const TCHAR* IndustrialTankRecipePath = TEXT("/Game/FactoryGame/Recipes/Buildings/Recipe_IndustrialTank.Recipe_IndustrialTank_C");

UAdvancedFluidBufferWorldModule::UAdvancedFluidBufferWorldModule()
{
	// Without this SML never instantiates a native module, and silently so.
	bRootModule = true;
}

void UAdvancedFluidBufferWorldModule::DispatchLifecycleEvent(ELifecyclePhase phase)
{
	Super::DispatchLifecycleEvent(phase);
	if (phase != ELifecyclePhase::POST_INITIALIZATION) return;

	// Runs on clients too, so their HUB shows the building among the milestone's unlocks.
	const TSubclassOf<UFGSchematic> schematic = PatchIndustrialTankSchematic();
	if (!schematic) return;

	UWorld* world = GetWorld();
	if (!world || world->GetNetMode() == NM_Client) return;

	// A save that bought the milestone before this mod was installed never ran the patched
	// unlock, so grant the recipe here. Adding an already-available recipe does nothing.
	AFGSchematicManager* schematics = AFGSchematicManager::Get(world);
	AFGRecipeManager* recipes = AFGRecipeManager::Get(world);
	if (schematics && recipes && schematics->IsSchematicPurchased(schematic) && !recipes->IsRecipeAvailable(mRecipe))
	{
		recipes->AddAvailableRecipe(mRecipe);
		UE_LOG(LogAdvancedFluidBuffer, Log, TEXT("%s already purchased, granted %s"), *schematic->GetName(), *mRecipe->GetName());
	}
}

TSubclassOf<UFGSchematic> UAdvancedFluidBufferWorldModule::PatchIndustrialTankSchematic()
{
	mRecipe = LoadClass<UFGRecipe>(nullptr, RecipePath);
	mIndustrialTankRecipe = LoadClass<UFGRecipe>(nullptr, IndustrialTankRecipePath);
	if (!mRecipe || !mIndustrialTankRecipe)
	{
		UE_LOG(LogAdvancedFluidBuffer, Error, TEXT("Could not load recipe classes: ours=%d industrialTank=%d"), mRecipe != nullptr, mIndustrialTankRecipe != nullptr);
		return nullptr;
	}

	AFGSchematicManager* schematics = AFGSchematicManager::Get(GetWorld());
	if (!schematics)
	{
		UE_LOG(LogAdvancedFluidBuffer, Error, TEXT("No schematic manager in this world"));
		return nullptr;
	}

	// UFGUnlockRecipe::AddRecipe is editor-only, so write mRecipes through reflection.
	FArrayProperty* recipesProp = FindFProperty<FArrayProperty>(UFGUnlockRecipe::StaticClass(), TEXT("mRecipes"));
	if (!recipesProp)
	{
		UE_LOG(LogAdvancedFluidBuffer, Error, TEXT("UFGUnlockRecipe::mRecipes not found"));
		return nullptr;
	}

	TArray<TSubclassOf<UFGSchematic>> all;
	schematics->GetAllSchematics(all);
	for (const TSubclassOf<UFGSchematic>& schematic : all)
	{
		if (!schematic) continue;
		for (UFGUnlock* unlock : UFGSchematic::GetUnlocks(schematic))
		{
			UFGUnlockRecipe* recipeUnlock = Cast<UFGUnlockRecipe>(unlock);
			if (!recipeUnlock) continue;

			TArray<TSubclassOf<UFGRecipe>>* list = recipesProp->ContainerPtrToValuePtr<TArray<TSubclassOf<UFGRecipe>>>(recipeUnlock);
			if (!list->Contains(mIndustrialTankRecipe)) continue;

			if (!list->Contains(mRecipe))
			{
				list->Add(mRecipe);
				UE_LOG(LogAdvancedFluidBuffer, Log, TEXT("Added %s to %s (unlocks the Industrial Fluid Buffer)"), *mRecipe->GetName(), *schematic->GetName());
			}
			else
			{
				UE_LOG(LogAdvancedFluidBuffer, Log, TEXT("%s already unlocks %s"), *schematic->GetName(), *mRecipe->GetName());
			}
			return schematic;
		}
	}

	UE_LOG(LogAdvancedFluidBuffer, Error, TEXT("No schematic among %d unlocks Recipe_IndustrialTank; the Advanced Fluid Buffer stays locked"), all.Num());
	return nullptr;
}
