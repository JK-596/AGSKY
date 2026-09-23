import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math

def acres_to_meters(acres):
    return acres * 4046.856

def calculate_grid(lat, lon, acres):
    total_area_m2 = acres_to_meters(acres)
    side_m = math.sqrt(total_area_m2)
    sub_side_m = side_m / 3

    # Degrees per meter
    lat_deg_per_m = 1 / 111320
    lon_deg_per_m = 1 / (111320 * math.cos(math.radians(lat)))

    sub_lat = sub_side_m * lat_deg_per_m
    sub_lon = sub_side_m * lon_deg_per_m

    # Bottom-left corner of full grid
    start_lat = lat - (1.5 * sub_lat)
    start_lon = lon - (1.5 * sub_lon)

    return start_lat, start_lon, sub_lat, sub_lon

def get_grid_labels():
    # Row 0 = bottom, Row 2 = top (North)
    return [
        ["SW", "S",      "SE"],
        ["W",  "CENTER", "E" ],
        ["NW", "N",      "NE"],
    ]

def get_box_style(label):
    """Returns (linewidth, linestyle) based on box type."""
    if label == "CENTER":
        return 3, "solid"
    elif label in ["N", "S", "E", "W"]:
        return 1.5, "solid"
    else:
        return 1.2, "--"

def plot_grid(lat, lon, acres):
    start_lat, start_lon, sub_lat, sub_lon = calculate_grid(lat, lon, acres)
    labels = get_grid_labels()

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_aspect('equal')
    ax.axis('off')

    for row in range(3):
        for col in range(3):
            label = labels[row][col]
            lw, ls = get_box_style(label)

            box_lon = start_lon + col * sub_lon
            box_lat = start_lat + row * sub_lat

            rect = patches.FancyBboxPatch(
                (box_lon, box_lat),
                sub_lon, sub_lat,
                boxstyle="square,pad=0",
                linewidth=lw,
                linestyle=ls,
                edgecolor='black',
                facecolor='white'
            )
            ax.add_patch(rect)

            # Label text
            center_x = box_lon + sub_lon / 2
            center_y = box_lat + sub_lat / 2

            fontsize = 13 if label == "CENTER" else 11
            fontweight = 'bold' if label == "CENTER" else 'normal'

            ax.text(
                center_x, center_y, label,
                ha='center', va='center',
                fontsize=fontsize,
                fontweight=fontweight,
                color='black'
            )

    # Set axis limits with padding
    padding_lon = sub_lon * 0.3
    padding_lat = sub_lat * 0.3
    ax.set_xlim(start_lon - padding_lon, start_lon + 3 * sub_lon + padding_lon)
    ax.set_ylim(start_lat - padding_lat, start_lat + 3 * sub_lat + padding_lat)

    # Coordinate labels on axes
    ax.set_xticks([start_lon + i * sub_lon for i in range(4)])
    ax.set_xticklabels(
        [f"{start_lon + i * sub_lon:.5f}°" for i in range(4)],
        fontsize=7, rotation=20
    )
    ax.set_yticks([start_lat + i * sub_lat for i in range(4)])
    ax.set_yticklabels(
        [f"{start_lat + i * sub_lat:.5f}°" for i in range(4)],
        fontsize=7
    )
    ax.tick_params(left=True, bottom=True, labelleft=True, labelbottom=True)

    # Title
    ax.set_title(
        f"Farm Grid System | Total Area: {acres} Acres",
        fontsize=15, fontweight='bold', pad=15
    )

    # Subtitle with coordinates
    fig.text(
        0.5, 0.01,
        f"Center: {lat:.6f}°N, {lon:.6f}°E",
        ha='center', fontsize=9, color='gray'
    )

    plt.tight_layout()
    plt.show()

def main():
    print("=" * 45)
    print("       AGSKY Farm Grid Visualizer")
    print("=" * 45)

    try:
        lat = float(input("Enter Latitude  (e.g. 11.0168): "))
        lon = float(input("Enter Longitude (e.g. 76.9558): "))
        acres = float(input("Enter Area in Acres (e.g. 5): "))
    except ValueError:
        print("❌ Invalid input. Please enter numeric values.")
        return

    print(f"\n📐 Calculating grid for {acres} acres at ({lat}, {lon})...")
    plot_grid(lat, lon, acres)

if __name__ == "__main__":
    main()