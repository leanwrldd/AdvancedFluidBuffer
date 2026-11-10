#include "AdvancedFluidBufferBuildable.h"

#include "AdvancedFluidBuffer.h"
#include "FGPipeConnectionComponent.h"
#include "FGPipeConnectionFactory.h"
#include "FGPipeSubsystem.h"
#include "FGInventoryComponent.h"
#include "Hologram/FGFactoryHologram.h"
#include "Resources/FGItemDescriptor.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Net/UnrealNetwork.h"

static const FName LiquidMeshTag(TEXT("AdvancedFluidBuffer_Liquid"));
static const FName FluidColorParam(TEXT("FluidColor"));

AAdvancedFluidBuffer::AAdvancedFluidBuffer()
{
	// AFGBuildable leaves the factory tick off; the controlled ports are driven from it.
	mFactoryTickFunction.bCanEverTick = true;
	mFactoryTickFunction.bStartWithTickEnabled = true;

	// Factory_Tick runs on worker threads (AFGBuildableSubsystem::TickFactoryActors uses
	// ParallelFor), so anything touching components, materials or other actors happens here,
	// on the game thread. A few updates a second is plenty for the sight glass.
	// AFGBuildablePipeReservoir already ticks every frame (it smooths the UI gauges).
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	mStorageCapacity = 400.f;
	mStackingHeight = 800.f; // tank height; the fluid sim's box height comes from it

	// The reservoir's own hologram stacks buffers on top of each other, which this model's roof
	// railing and side ports are not built for. Place it like any other factory building.
	mHologramClass = AFGFactoryHologram::StaticClass();
}

void AAdvancedFluidBuffer::Tick(float dt)
{
	Super::Tick(dt);

	if (HasAuthority())
	{
		// Requested from Factory_Tick; the pipe subsystem must only be called on the game thread.
		if (UClass* wanted = mPendingNetworkFluid.exchange(nullptr))
		{
			const int32 networkID = mFreeFlowPort ? mFreeFlowPort->GetPipeNetworkID() : INDEX_NONE;
			AFGPipeSubsystem* pipes = AFGPipeSubsystem::Get(GetWorld());
			if (pipes && networkID != INDEX_NONE && !GetTankFluid())
			{
				pipes->TrySetNetworkFluidDescriptor(networkID, wanted);
			}
		}
	}

	if (mAppliedFill != mReplicatedFill || mAppliedFluid != mReplicatedFluid)
	{
		UpdateLiquidVisual();
	}
}

template <class T>
T* AAdvancedFluidBuffer::FindPort(const TArray<UFGPipeConnectionComponent*>& ports, const TCHAR* key) const
{
	const FName tag(key);
	for (UFGPipeConnectionComponent* port : ports)
	{
		if (port->ComponentHasTag(tag)) return Cast<T>(port);
	}
	for (UFGPipeConnectionComponent* port : ports)
	{
		if (port->GetName().Contains(key)) return Cast<T>(port);
	}
	return nullptr;
}

TArray<UFGPipeConnectionComponent*> AAdvancedFluidBuffer::GetPipeConnections()
{
	TArray<UFGPipeConnectionComponent*> result;
	if (mFreeFlowPort) result.Add(mFreeFlowPort);
	return result;
}

bool AAdvancedFluidBuffer::IsFluidIntegrantRegistered() const
{
	// Same conditions under which AFGBuildablePipeReservoir::BeginPlay registers (1.2 shipping DLL).
	return mFreeFlowPort && HasAuthority() && GetBlueprintDesigner() == nullptr;
}

void AAdvancedFluidBuffer::RestrictReservoirConnections()
{
	// The reservoir fills its private mPipeConnections with every pipe connection on the actor,
	// controlled ports included. Its GetFluidDescriptor reads element 0 and GetFlowLimit and the
	// UI gauges scale with the count, so both must only ever see FreeFlow.
	static FArrayProperty* prop = FindFProperty<FArrayProperty>(AFGBuildablePipeReservoir::StaticClass(), TEXT("mPipeConnections"));
	if (!prop || !mFreeFlowPort)
	{
		UE_LOG(LogAdvancedFluidBuffer, Error, TEXT("%s: could not restrict reservoir connections (prop=%d freeFlow=%d)"), *GetName(), prop != nullptr, mFreeFlowPort != nullptr);
		return;
	}
	auto* list = prop->ContainerPtrToValuePtr<TArray<TObjectPtr<UFGPipeConnectionComponent>>>(this);
	list->Reset();
	list->Add(mFreeFlowPort);
}

void AAdvancedFluidBuffer::ConfigureFluidBox()
{
	// Mirrors AFGBuildablePipeReservoir::BeginPlay: Z/LowZ/HighZ are the port heights in world
	// meters, Height is the building's height, laminar height 1.5 m, 1% overfill.
	const float portZ = (mFreeFlowPort ? mFreeFlowPort->GetComponentLocation().Z : GetActorLocation().Z) * 0.01f;
	mFluidBox.Z = portZ;
	mFluidBox.LowZ = portZ;
	mFluidBox.HighZ = portZ;
	mFluidBox.Height = mStackingHeight * 0.01f;
	mFluidBox.LaminarHeight = FMath::Min(1.5f, mFluidBox.Height);
	mFluidBox.MaxContent = mStorageCapacity;
	mFluidBox.MaxOverfillPct = 0.01f;
}

void AAdvancedFluidBuffer::BeginPlay()
{
	TArray<UFGPipeConnectionComponent*> ports;
	GetComponents<UFGPipeConnectionComponent>(ports);

	mFreeFlowPort = FindPort<UFGPipeConnectionComponent>(ports, TEXT("FreeFlow"));
	if (mFreeFlowPort && mFreeFlowPort->IsA<UFGPipeConnectionFactory>())
	{
		UE_LOG(LogAdvancedFluidBuffer, Error, TEXT("%s: FreeFlow must be a plain FGPipeConnectionComponent, not FGPipeConnectionFactory."), *GetName());
		mFreeFlowPort = nullptr;
	}
	mControlledOutlet = FindPort<UFGPipeConnectionFactory>(ports, TEXT("ControlledOutlet"));
	mControlledInlet = FindPort<UFGPipeConnectionFactory>(ports, TEXT("ControlledInlet"));

	// The hologram reads connection types from the Blueprint template, so set them there too.
	// This only guards against a mis-set Blueprint at runtime.
	if (mFreeFlowPort) mFreeFlowPort->SetPipeConnectionType(EPipeConnectionType::PCT_ANY);
	if (mControlledOutlet)
	{
		mControlledOutlet->SetPipeConnectionType(EPipeConnectionType::PCT_PRODUCER);
		mControlledOutlet->SetInventoryAccessIndex(0);
	}
	if (mControlledInlet)
	{
		mControlledInlet->SetPipeConnectionType(EPipeConnectionType::PCT_CONSUMER);
		mControlledInlet->SetInventoryAccessIndex(0);
	}

	// Registers the fluid box (asking GetPipeConnections, which returns only FreeFlow) and sets
	// it up from two of the actor's pipe connections; it needs at least two, which it has.
	Super::BeginPlay();
	RestrictReservoirConnections();

	if (!mFreeFlowPort || !mControlledOutlet || !mControlledInlet)
	{
		UE_LOG(LogAdvancedFluidBuffer, Error,
			TEXT("%s: missing port(s) freeFlow=%d controlledOutlet=%d controlledInlet=%d (found %d pipe connections). Tag or name them FreeFlow / ControlledOutlet / ControlledInlet."),
			*GetName(), mFreeFlowPort != nullptr, mControlledOutlet != nullptr, mControlledInlet != nullptr, ports.Num());
	}

	// Redo the box from FreeFlow alone; the reservoir used whichever two connections came first.
	ConfigureFluidBox();
	if (HasAuthority())
	{
		// A save made with a larger capacity: clamp to the overfill limit.
		mFluidBox.Content = FMath::Clamp(mFluidBox.Content, 0.f, mFluidBox.MaxContent * (1.f + mFluidBox.MaxOverfillPct));
	}

	TArray<UStaticMeshComponent*> meshes;
	GetComponents<UStaticMeshComponent>(meshes);
	for (UStaticMeshComponent* mesh : meshes)
	{
		if (mesh->ComponentHasTag(LiquidMeshTag))
		{
			mLiquidMesh = mesh;
			mLiquidFullScaleZ = mesh->GetRelativeScale3D().Z;
			break;
		}
	}

	if (HasAuthority()) UpdateReplicatedState();
	UpdateLiquidVisual();
}

void AAdvancedFluidBuffer::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(AAdvancedFluidBuffer, mReplicatedFluid);
	DOREPLIFETIME(AAdvancedFluidBuffer, mReplicatedFill);
}

TSubclassOf<UFGItemDescriptor> AAdvancedFluidBuffer::GetTankFluid() const
{
	return mFreeFlowPort ? mFreeFlowPort->GetFluidDescriptor() : nullptr;
}

void AAdvancedFluidBuffer::Factory_Tick(float dt)
{
	Super::Factory_Tick(dt);
	if (!IsFluidIntegrantRegistered()) return;

	// Outlet first, so fluid that arrived through FreeFlow above the threshold leaves before
	// the inlet looks at the level.
	TickControlledOutlet(dt);
	TickControlledInlet(dt);

	UpdateReplicatedState();
}

void AAdvancedFluidBuffer::TickControlledOutlet(float dt)
{
	if (!mControlledOutlet) return;

	const TSubclassOf<UFGItemDescriptor> fluid = GetTankFluid();
	const float excess = mFluidBox.Content - mFluidBox.MaxContent * mOutputThreshold; // [m3]
	const int32 maxLiters = FMath::FloorToInt(excess * 1000.f);
	if (!fluid || maxLiters <= 0) return;

	const int32 pushed = mControlledOutlet->Factory_PushPipeOutput(dt, FInventoryStack(maxLiters, fluid));
	if (pushed > 0)
	{
		mFluidBox.Content = FMath::Max(0.f, mFluidBox.Content - FMath::Min(pushed, maxLiters) * 0.001f);
	}
}

void AAdvancedFluidBuffer::TickControlledInlet(float dt)
{
	if (!mControlledInlet) return;

	const float room = mFluidBox.MaxContent * mInputThreshold - mFluidBox.Content; // [m3]
	const int32 maxLiters = FMath::FloorToInt(room * 1000.f);
	if (maxLiters <= 0) return;

	const TSubclassOf<UFGItemDescriptor> incoming = mControlledInlet->GetFluidDescriptor();
	if (!incoming) return;

	const TSubclassOf<UFGItemDescriptor> tankFluid = GetTankFluid();
	if (!tankFluid)
	{
		// The tank's network has no fluid type yet. Ask for the incoming one (Tick does it on the
		// game thread) and wait for it to arrive before adding content, so the network never
		// holds fluid of no type.
		mPendingNetworkFluid.store(incoming.Get());
		return;
	}
	if (tankFluid != incoming) return;

	FInventoryStack pulled;
	if (mControlledInlet->Factory_PullPipeInput(dt, pulled, incoming, maxLiters) && pulled.NumItems > 0)
	{
		mFluidBox.Content += FMath::Min(pulled.NumItems, maxLiters) * 0.001f;
	}
}

void AAdvancedFluidBuffer::UpdateReplicatedState()
{
	uint8 fill = 0;
	if (mFluidBox.Content > KINDA_SMALL_NUMBER && mFluidBox.MaxContent > 0.f)
	{
		// Never show an empty glass while there is fluid in the tank.
		fill = (uint8)FMath::Clamp(FMath::RoundToInt(255.f * mFluidBox.Content / mFluidBox.MaxContent), 1, 255);
	}
	const TSubclassOf<UFGItemDescriptor> fluid = fill > 0 ? GetTankFluid() : nullptr;

	// Worker thread: only store the values. Tick applies them to the mesh on the game thread
	// (OnRep does not fire on the server itself).
	mReplicatedFill = fill;
	mReplicatedFluid = fluid;
}

void AAdvancedFluidBuffer::OnRep_Visuals()
{
	UpdateLiquidVisual();
}

void AAdvancedFluidBuffer::UpdateLiquidVisual()
{
	// Game thread only: components and material instances talk to the renderer.
	check(IsInGameThread());

	const bool fluidChanged = mAppliedFluid != mReplicatedFluid;
	mAppliedFill = mReplicatedFill;
	mAppliedFluid = mReplicatedFluid;
	if (!mLiquidMesh) return;

	const float fill = mAppliedFill / 255.f;
	const bool visible = fill > 0.f && mAppliedFluid != nullptr;
	mLiquidMesh->SetVisibility(visible);
	if (!visible) return;

	FVector scale = mLiquidMesh->GetRelativeScale3D();
	scale.Z = mLiquidFullScaleZ * fill;
	mLiquidMesh->SetRelativeScale3D(scale);

	if (!mLiquidMaterial)
	{
		mLiquidMaterial = mLiquidMesh->CreateDynamicMaterialInstance(0);
	}
	if (mLiquidMaterial && (fluidChanged || !mAppliedColorOnce))
	{
		mLiquidMaterial->SetVectorParameterValue(FluidColorParam, UFGItemDescriptor::GetFluidColorLinear(mAppliedFluid));
		mAppliedColorOnce = true;
	}
}
