#pragma once

#include <atomic>
#include "CoreMinimal.h"
#include "Buildables/FGBuildablePipeReservoir.h"
#include "AdvancedFluidBufferBuildable.generated.h"

class UFGPipeConnectionComponent;
class UFGPipeConnectionFactory;
class UFGItemDescriptor;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;

/**
 * A fluid tank with three pipe ports:
 *   FreeFlow          - two-way, exactly like a vanilla Fluid Buffer port. The game's own fluid
 *                       sim moves fluid in or out of the tank through it.
 *   ControlledOutlet  - only releases fluid while the tank is above mOutputThreshold (75%).
 *   ControlledInlet   - only accepts fluid while the tank is below mInputThreshold (75%).
 *
 * How the ports are split between pipe networks:
 * - The tank IS a vanilla Fluid Buffer (AFGBuildablePipeReservoir subclass), so it registers its
 *   mFluidBox like one, and the vanilla buffer widget (Widget_PipeStorageTank) works on it as-is.
 *   FreeFlow is a plain UFGPipeConnectionComponent and the only port the reservoir knows about
 *   (GetPipeConnections and the reservoir's private mPipeConnections are both cut down to it),
 *   so FreeFlow and the tank share one network and the game simulates that port.
 * - The two controlled ports are UFGPipeConnectionFactory components. Each owns a small fluid
 *   box of its own and joins its own network, so the game never moves fluid through them by
 *   itself. Factory_Tick moves fluid between those boxes and mFluidBox, gated by the fill level.
 *
 * The fluid type is the FreeFlow network's type. When that network has none yet, fluid arriving
 * at the controlled inlet sets it.
 *
 * Blueprint subclass (Build_AdvancedFluidBuffer) needs:
 * - One UFGPipeConnectionComponent (connection type Any) tagged or named "FreeFlow".
 * - Two UFGPipeConnectionFactory components tagged or named "ControlledOutlet" (Producer) and
 *   "ControlledInlet" (Consumer).
 *   Each port sits on its mesh socket with its forward axis pointing out of the port.
 * - mStackingHeight set to the tank's height (the fluid sim's box height) and mStorageCapacity.
 * - mIsUseable and mInteractWidgetSoftClass = Widget_PipeStorageTank for the vanilla buffer UI.
 * - Optionally a StaticMeshComponent tagged "AdvancedFluidBuffer_Liquid" with its origin at its bottom.
 *   It is scaled on Z to the fill level and gets a "FluidColor" vector parameter. Keep it a
 *   plain StaticMeshComponent, not part of the buildable's instanced mesh data, or it cannot be
 *   scaled per building.
 */
UCLASS()
class ADVANCEDFLUIDBUFFER_API AAdvancedFluidBuffer : public AFGBuildablePipeReservoir
{
	GENERATED_BODY()

public:
	AAdvancedFluidBuffer();

	// Begin AActor
	virtual void BeginPlay() override;
	virtual void Tick(float dt) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
	// End AActor

	// Begin AFGBuildable
	virtual void Factory_Tick(float dt) override;
	// End AFGBuildable

	// Begin IFGFluidIntegrantInterface
	/** Only FreeFlow belongs to the tank's network; the controlled ports are integrants of their own. */
	virtual TArray<UFGPipeConnectionComponent*> GetPipeConnections() override;
	// End IFGFluidIntegrantInterface

	// GetFluidContent, GetFluidContentMax, GetFlowFill/Drain and GetFluidDescriptor come from
	// AFGBuildablePipeReservoir and are what the vanilla widget reads.

	/** Fill level in [0,1]. Valid on clients (quantized to 1/255). */
	UFUNCTION(BlueprintPure, Category = "Advanced Fluid Buffer")
	float GetFillFraction() const { return mReplicatedFill / 255.f; }

	/** The fluid in the tank, null when empty. Valid on clients. */
	UFUNCTION(BlueprintPure, Category = "Advanced Fluid Buffer")
	TSubclassOf<UFGItemDescriptor> GetStoredFluid() const { return mReplicatedFluid; }

protected:
	// The base factory would move fluid through pipe connections on its own. All controlled
	// movement happens in Factory_Tick, so these stay empty.
	virtual void Factory_PullPipeInput_Implementation(float dt) override {}
	virtual void Factory_PushPipeOutput_Implementation(float dt) override {}

	/** The controlled outlet releases fluid only above this fill fraction. */
	UPROPERTY(EditDefaultsOnly, Category = "Advanced Fluid Buffer", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float mOutputThreshold = 0.75f;

	/** The controlled inlet accepts fluid only below this fill fraction. */
	UPROPERTY(EditDefaultsOnly, Category = "Advanced Fluid Buffer", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float mInputThreshold = 0.75f;

	/** Ports, found in BeginPlay among the Blueprint's components. */
	UPROPERTY(Transient, BlueprintReadOnly, Category = "Advanced Fluid Buffer")
	TObjectPtr<UFGPipeConnectionComponent> mFreeFlowPort;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "Advanced Fluid Buffer")
	TObjectPtr<UFGPipeConnectionFactory> mControlledOutlet;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "Advanced Fluid Buffer")
	TObjectPtr<UFGPipeConnectionFactory> mControlledInlet;

private:
	/** Finds the component whose tag or name matches key. */
	template <class T>
	T* FindPort(const TArray<UFGPipeConnectionComponent*>& ports, const TCHAR* key) const;

	/** Sets the fluid box geometry the way AFGBuildablePipeReservoir::BeginPlay does. */
	void ConfigureFluidBox();

	/** True when the reservoir registered its fluid box with the pipe subsystem (server, not in a designer). */
	bool IsFluidIntegrantRegistered() const;

	/** Cuts the reservoir's private connection list down to FreeFlow, by reflection. */
	void RestrictReservoirConnections();

	/** The fluid type of the FreeFlow network, i.e. the tank's fluid. */
	TSubclassOf<UFGItemDescriptor> GetTankFluid() const;

	void TickControlledInlet(float dt);
	void TickControlledOutlet(float dt);

	/** Server: refresh the replicated values. */
	void UpdateReplicatedState();

	UFUNCTION()
	void OnRep_Visuals();

	/** Applies the fill level and fluid color to the liquid mesh, on every machine. */
	void UpdateLiquidVisual();

	UPROPERTY(ReplicatedUsing = OnRep_Visuals)
	TSubclassOf<UFGItemDescriptor> mReplicatedFluid;

	/** Fill level quantized to a byte, 0..255. */
	UPROPERTY(ReplicatedUsing = OnRep_Visuals)
	uint8 mReplicatedFill = 0;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> mLiquidMesh;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> mLiquidMaterial;

	/** The liquid mesh's authored Z scale, i.e. its scale at 100% full. */
	float mLiquidFullScaleZ = 1.f;

	/** What the liquid mesh currently shows (game thread only). */
	uint8 mAppliedFill = 0;
	UPROPERTY(Transient)
	TSubclassOf<UFGItemDescriptor> mAppliedFluid;
	bool mAppliedColorOnce = false;

	/**
	 * Fluid type the FreeFlow network should take on. Written by Factory_Tick (a worker thread),
	 * consumed by Tick on the game thread, where the pipe subsystem may be called.
	 * Item descriptor classes stay loaded, so a raw pointer is safe here.
	 */
	std::atomic<UClass*> mPendingNetworkFluid{nullptr};
};
